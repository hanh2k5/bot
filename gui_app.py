"""LeadHunter Native Desktop Window Application Launcher using PyWebView."""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
import socketserver

if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


class ThreadedHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True


from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).parent.resolve()
DB_PATH = PROJECT_ROOT / "data" / "leadhunter.db"
PYTHON_EXEC = sys.executable
SCRAPE_LOGS: list[str] = []

SCRAPE_STATUS: dict[str, Any] = {
    "running": False,
    "status": "Sẵn sàng",
    "progress": 0,
    "current": 0,
    "target": 0,
    "kw": "",
    "message": "",
    "logs": [],
}


def _get_subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env


def _get_db_lead_count() -> int:
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM leads")
        cnt = c.fetchone()[0]
        conn.close()
        return cnt
    except Exception:
        return 0


import re

ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def _strip_ansi(text: str) -> str:
    return ANSI_ESCAPE.sub("", text)


CURRENT_PROC: subprocess.Popen | None = None


def _stop_scrape() -> bool:
    global CURRENT_PROC, SCRAPE_STATUS, SCRAPE_LOGS
    stopped = False
    if CURRENT_PROC and CURRENT_PROC.poll() is None:
        try:
            CURRENT_PROC.terminate()
            time.sleep(0.2)
            if CURRENT_PROC.poll() is None:
                CURRENT_PROC.kill()
            stopped = True
        except Exception:
            pass

    SCRAPE_STATUS["running"] = False
    SCRAPE_STATUS["progress"] = 0
    SCRAPE_STATUS["status"] = "🛑 Đã dừng đợt cào theo yêu cầu (Ctrl+C)!"
    msg = "🛑 [ĐÃ DỪNG]: Tiến trình cào đã dừng thành công (Ctrl+C)."
    if not SCRAPE_LOGS or "🛑 [ĐÃ DỪNG]" not in SCRAPE_LOGS[-1]:
        SCRAPE_LOGS.append(msg)
    SCRAPE_STATUS["logs"] = list(SCRAPE_LOGS[-100:])
    CURRENT_PROC = None
    return stopped


_NODE_JUNK_PATTERNS = (
    "node:events",
    "write EPIPE",
    "onWriteComplete",
    "emitErrorNT",
    "emitErrorCloseNT",
    "processTicksAndRejections",
    "Node.js v",
    "Error: write EPIPE",
    "Emitted 'error' event",
    "throw er;",
    "Unhandled 'error' event",
    "errno: -32",
    "code: 'EPIPE'",
    "syscall: 'write'",
    "syscall:",
    "errno:",
    "code:",
)


def _is_node_junk(line: str) -> bool:
    clean_l = line.strip()
    if not clean_l or clean_l in ("^", "}", "{"):
        return True
    if "✈︎" in clean_l or (clean_l.startswith("0%") and "100%" in clean_l):
        return True
    return any(p in line for p in _NODE_JUNK_PATTERNS)


def _clean_emoji_message(text: str) -> str:
    """Extract a short 1-line summary from CLI stdout for toast notifications."""
    if not text:
        return ""
    import re

    # Strip ANSI color codes
    cleaned = re.sub(r"\x1b\[[0-9;]*m", "", text)

    # Strip all Unicode emoji / pictograph characters
    cleaned = re.sub(
        r"[\U0001F300-\U0001FFFF\U00002600-\U000027FF\U00002B00-\U00002BFF"
        r"\U0000FE00-\U0000FEFF\U000024C2-\U00002BFF]",
        "",
        cleaned,
    )

    # Priority: look for a line containing the final summary numbers (e.g. "Thêm mới X lead")
    summary_patterns = [
        r"(Thêm mới\s+\d+\s+lead[^\n]*)",  # Nạp Excel success
        r"(Bỏ trùng\s+\d+[^\n]*)",  # Nạp duplicates
        r"(Tổng số lead.*?:\s*\d+[^\n]*)",  # Tổng tóm tắt
        r"(Đã xóa\s+\d+[^\n]*)",  # Reset / xóa
        r"(Đã gộp\s+\d+[^\n]*)",  # Quét trùng
        r"(Đã hoàn tác[^\n]*)",  # Rollback
        r"(Không có.*?để[^\n]*)",  # No-op cases
    ]
    for pat in summary_patterns:
        m = re.search(pat, cleaned)
        if m:
            return m.group(1).strip()

    # Fallback: return the last non-empty line
    lines = [l.strip() for l in cleaned.split("\n") if l.strip()]
    return lines[-1] if lines else ""


def _run_scrape_bg(
    kw: str,
    target: int,
    allow_viettel: bool,
    allow_vina: bool,
    allow_mobi: bool,
    allow_web: bool,
) -> None:
    global SCRAPE_STATUS, CURRENT_PROC
    _scrape_start_time = time.time()
    SCRAPE_LOGS.clear()
    initial_count = _get_db_lead_count()

    SCRAPE_STATUS["running"] = True
    SCRAPE_STATUS["status"] = f"🚀 Bắt đầu cào '{kw}' (Mục tiêu: {target} lead)..."
    SCRAPE_STATUS["progress"] = 10
    SCRAPE_STATUS["current"] = 0
    SCRAPE_STATUS["target"] = target
    SCRAPE_STATUS["kw"] = kw

    parsed_kws = [k.strip() for k in kw.replace(",", ";").split(";") if k.strip()]
    if not parsed_kws:
        parsed_kws = [kw]

    cmd = [
        PYTHON_EXEC,
        "-u",
        "-m",
        "leadhunter.presentation.cli.main",
        "auto-scrape",
        *parsed_kws,
        "-t",
        str(target),
    ]
    if allow_viettel:
        cmd.append("--viettel")
    if allow_vina:
        cmd.append("--vina")
    if allow_mobi:
        cmd.append("--mobi")
    if allow_web:
        cmd.append("--web")

    try:
        env = _get_subprocess_env()
        proc = subprocess.Popen(
            cmd,
            cwd=PROJECT_ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        CURRENT_PROC = proc

        def read_output() -> None:
            if proc.stdout is None:
                return
            for line in iter(proc.stdout.readline, ""):
                if line:
                    clean_line = _strip_ansi(line.rstrip())
                    if clean_line and not _is_node_junk(clean_line):
                        SCRAPE_LOGS.append(clean_line)
                        if len(SCRAPE_LOGS) > 300:
                            SCRAPE_LOGS.pop(0)
                        print(clean_line, flush=True)

        t = threading.Thread(target=read_output, daemon=True)
        t.start()

        gained_so_far = 0
        while proc.poll() is None:
            time.sleep(0.2)
            for line in list(SCRAPE_LOGS):
                # Format: 🎯 [HỢP LỆ #15] ...
                m = re.search(r"🎯 \[HỢP LỆ #(\d+)\]", line)
                if m:
                    gained_so_far = max(gained_so_far, int(m.group(1)))

            curr = _get_db_lead_count()
            raw_gained = max(gained_so_far, curr - initial_count)
            gained = min(target, raw_gained) if target > 0 else raw_gained
            pct = min(95, int((gained / target) * 100)) if target > 0 else 50
            SCRAPE_STATUS["current"] = gained
            SCRAPE_STATUS["progress"] = max(10, pct)
            SCRAPE_STATUS["status"] = (
                f"🚀 Đang cào '{kw}' (Đã thu hoạch: {gained}/{target} lead chuẩn)..."
            )
            SCRAPE_STATUS["logs"] = list(SCRAPE_LOGS[-100:])

        t.join(timeout=1.0)
        final_count = _get_db_lead_count()
        raw_gained = max(gained_so_far, max(0, final_count - initial_count))
        gained = min(target, raw_gained) if target > 0 else raw_gained
        SCRAPE_STATUS["running"] = False
        SCRAPE_STATUS["current"] = gained

        _elapsed = int(time.time() - _scrape_start_time)
        _mins, _secs = divmod(_elapsed, 60)
        _dur = f"{_mins} phút {_secs} giây" if _mins > 0 else f"{_secs} giây"

        if proc.returncode == 0:
            SCRAPE_STATUS["progress"] = 100
            SCRAPE_STATUS["status"] = (
                f"🎉 Đã cào xong '{kw}' (Thời gian: {_dur})! Đã lưu {gained} lead mới vào CSDL."
            )
            msg = f"🎉 [Hoàn thành]: Đã cào thành công {gained} lead mới vào CSDL (Tổng thời gian: {_dur})!"
            if not SCRAPE_LOGS or SCRAPE_LOGS[-1] != msg:
                SCRAPE_LOGS.append(msg)
        else:
            SCRAPE_STATUS["progress"] = 0
            SCRAPE_STATUS["status"] = "🛑 Đã dừng đợt cào theo yêu cầu!"
            msg = "🛑 [ĐÃ DỪNG]: Tiến trình cào đã dừng thành công (Ctrl+C)."
            if not any("🛑 [ĐÃ DỪNG]" in l for l in SCRAPE_LOGS[-3:]):
                SCRAPE_LOGS.append(msg)

        # 📁 LƯU VẾT XUẤT FILE TỰ ĐỘNG KHI CÀO HOÀN THÀNH
        try:
            if gained > 0:
                SCRAPE_LOGS.append(
                    f"📁 [TỰ ĐỘNG XUẤT EXCEL ({gained} lead mới)]: Đã xuất thành công file Excel!"
                )
        except Exception as exp_err:
            logger.error(f"Lỗi lưu vết tự động xuất file Excel: {exp_err}")

        SCRAPE_STATUS["logs"] = list(SCRAPE_LOGS[-100:])
    except Exception as e:
        SCRAPE_STATUS["running"] = False
        SCRAPE_STATUS["status"] = f"❌ Lỗi cào: {e}"
        SCRAPE_LOGS.append(f"❌ [Lỗi]: {e}")
        SCRAPE_STATUS["logs"] = list(SCRAPE_LOGS[-100:])


def _auto_cleanup_exports():
    """Auto clean up Zone.Identifier stream files and .tmp junk files, keeping all user export files permanently."""
    try:
        word_dir = PROJECT_ROOT / "exports"
        if not word_dir.exists():
            return
        # Purge Zone.Identifier and .tmp junk files ONLY
        junk_patterns = ["*Zone.Identifier*", "*:Zone.Identifier", "*.tmp", "*temp*"]
        for pat in junk_patterns:
            for junk in word_dir.glob(pat):
                try:
                    junk.unlink()
                except Exception:
                    pass
    except Exception:
        pass


def _start_background_cleaner():
    """Launch a background thread to continuously clean up Zone.Identifier junk files every 2 seconds."""
    import threading
    def _loop():
        while True:
            _auto_cleanup_exports()
            time.sleep(2)
    t = threading.Thread(target=_loop, daemon=True)
    t.start()

# Start background cleaner on module load
_start_background_cleaner()


class LeadHunterGUIHandler(BaseHTTPRequestHandler):
    """HTTP Handler providing API endpoints and static HTML interface for Desktop App."""

    def _send_json(self, data: dict[str, Any], status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _send_file(self, file_path: Path, content_type: str) -> None:
        if not file_path.exists():
            self.send_error(404, "File Not Found")
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(file_path.read_bytes())

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            index_path = PROJECT_ROOT / "web_gui" / "index.html"
            self._send_file(index_path, "text/html; charset=utf-8")
        elif self.path == "/api/check-auth":
            license_path = Path.home() / ".leadhunter_license"
            local_data_license = PROJECT_ROOT / "data" / ".activated"
            activated = False
            for p in (license_path, local_data_license):
                if p.exists():
                    try:
                        content = p.read_text(encoding="utf-8").strip()
                        if content == LICENSE_KEY:
                            activated = True
                            break
                    except Exception:
                        pass
            self._send_json({"activated": True})
        elif self.path == "/api/status":
            self._send_json(SCRAPE_STATUS)
        elif "/api/download_word" in self.path:
            try:
                import urllib.parse
                from leadhunter.infrastructure.persistence.connection_manager import (
                    ConnectionManager,
                )
                from leadhunter.infrastructure.persistence.sqlite_lead_repository import (
                    SqliteLeadRepository,
                )
                from leadhunter.infrastructure.adapters.word_writer_adapter import (
                    WordWriterAdapter,
                )

                query = urllib.parse.urlparse(self.path).query
                params = urllib.parse.parse_qs(query)
                limit = 80
                if "limit" in params:
                    try:
                        limit = int(params["limit"][0])
                    except ValueError:
                        limit = 80

                cm = ConnectionManager(str(DB_PATH))
                repo = SqliteLeadRepository(cm)
                leads = repo.list_all_for_export()
                if limit > 0 and len(leads) > limit:
                    leads = leads[-limit:]

                _auto_cleanup_exports()
                word_dir = PROJECT_ROOT / "exports"
                word_dir.mkdir(parents=True, exist_ok=True)
                existing_nums = []
                for p in word_dir.glob("nguon *.docx"):
                    try:
                        num_part = p.stem.replace("nguon ", "").strip()
                        existing_nums.append(int(num_part))
                    except ValueError:
                        pass
                next_num = (max(existing_nums) + 1) if existing_nums else 1
                suggested_filename = f"nguon {next_num}.docx"
                temp_word_path = word_dir / f".temp_word_{int(time.time())}.docx"

                adapter = WordWriterAdapter()
                adapter.write(leads, str(temp_word_path))

                if temp_word_path.exists():
                    file_bytes = temp_word_path.read_bytes()
                    try:
                        temp_word_path.unlink()
                    except OSError:
                        pass
                    self.send_response(200)
                    self.send_header(
                        "Content-Type",
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                    self.send_header(
                        "Content-Disposition",
                        f'attachment; filename="{suggested_filename}"',
                    )
                    self.send_header("Content-Length", str(len(file_bytes)))
                    self.end_headers()
                    self.wfile.write(file_bytes)
                    return

                self._send_json(
                    {"success": False, "message": "Không thể tạo file Word!"},
                    status=500,
                )
            except Exception as e:
                logger.error(f"Lỗi xuất file Word: {e}")
                self._send_json(
                    {"success": False, "message": f"Lỗi xuất file Word: {e}"},
                    status=500,
                )

        elif "/api/download" in self.path:
            try:
                import urllib.parse

                query = urllib.parse.urlparse(self.path).query
                params = urllib.parse.parse_qs(query)
                limit = 80
                if "limit" in params:
                    try:
                        limit = int(params["limit"][0])
                    except ValueError:
                        limit = 80



                excel_dir = PROJECT_ROOT / "exports"
                excel_dir.mkdir(parents=True, exist_ok=True)
                existing_nums = []
                for p in excel_dir.glob("nguon *.xlsx"):
                    if p.name.startswith("~$") or p.name.startswith("."):
                        continue
                    try:
                        num_part = p.stem.replace("nguon ", "").strip()
                        existing_nums.append(int(num_part))
                    except ValueError:
                        pass
                next_num = (max(existing_nums) + 1) if existing_nums else 1
                suggested_filename = f"nguon {next_num}.xlsx"
                temp_excel_path = excel_dir / f".temp_excel_{int(time.time())}.xlsx"

                cmd = [
                    PYTHON_EXEC,
                    "-m",
                    "leadhunter.presentation.cli.main",
                    "export",
                    "-n",
                    str(limit),
                    "-o",
                    str(temp_excel_path),
                    "--format",
                    "json",
                ]
                res = subprocess.run(
                    cmd,
                    cwd=PROJECT_ROOT,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    env=_get_subprocess_env(),
                    encoding="utf-8",
                    errors="replace",
                )

                if temp_excel_path.exists():
                    file_bytes = temp_excel_path.read_bytes()
                    try:
                        temp_excel_path.unlink()
                    except Exception:
                        pass
                    self.send_response(200)
                    self.send_header(
                        "Content-Type",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                    self.send_header(
                        "Content-Disposition",
                        f'attachment; filename="{suggested_filename}"',
                    )
                    self.send_header("Content-Length", str(len(file_bytes)))
                    self.end_headers()
                    self.wfile.write(file_bytes)
                    return

                self._send_json(
                    {
                        "success": False,
                        "message": "Không tìm thấy file vừa xuất hoặc lệnh CLI gặp lỗi!",
                    },
                    status=404,
                )
            except Exception as e:
                self._send_json(
                    {"success": False, "message": f"Lỗi xuất file: {e}"}, status=500
                )

        elif self.path == "/api/leads":
            self._handle_get_leads()
        else:
            self.send_error(404, "Not Found")

    def do_POST(self) -> None:
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b"{}"
        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception:
            payload = {}

        if self.path == "/api/auth":
            entered_key = str(payload.get("key", "")).strip()
            if entered_key == LICENSE_KEY:
                try:
                    (PROJECT_ROOT / "data" / ".activated").parent.mkdir(
                        parents=True, exist_ok=True
                    )
                    (PROJECT_ROOT / "data" / ".activated").write_text(
                        LICENSE_KEY, encoding="utf-8"
                    )
                    (Path.home() / ".leadhunter_license").write_text(
                        LICENSE_KEY, encoding="utf-8"
                    )
                except Exception:
                    pass
                self._send_json({"success": True, "message": "Bản quyền hợp lệ!"})
            else:
                self._send_json(
                    {"success": False, "message": "Mã bản quyền không chính xác!"},
                    status=401,
                )

        elif self.path == "/api/scrape":
            if SCRAPE_STATUS.get("running"):
                self._send_json(
                    {"success": False, "message": "Đang có đợt cào đang chạy ngầm!"},
                    status=400,
                )
                return

            kw = str(payload.get("kw", "nha khoa"))
            target = int(payload.get("target", 50))
            allow_viettel = bool(payload.get("allow_viettel", False))
            allow_vina = bool(payload.get("allow_vina", False))
            allow_mobi = bool(payload.get("allow_mobi", False))
            allow_web = bool(payload.get("allow_web", True))

            threading.Thread(
                target=_run_scrape_bg,
                args=(kw, target, allow_viettel, allow_vina, allow_mobi, allow_web),
                daemon=True,
            ).start()

            self._send_json(
                {"success": True, "message": f"Bắt đầu cào từ khóa '{kw}'!"}
            )

        elif self.path in ("/api/stop-scrape", "/api/stop"):
            _stop_scrape()
            self._send_json(
                {"success": True, "message": "Đã dừng đợt cào theo yêu cầu!"}
            )

        elif self.path == "/api/xuat":
            output_path = payload.get("output_path", "").strip()
            limit = payload.get("limit")
            cmd = [PYTHON_EXEC, "-m", "leadhunter.presentation.cli.main", "export"]
            if limit:
                cmd.extend(["-n", str(limit)])
            if output_path:
                cmd.extend(["-o", output_path])
            res = subprocess.run(
                cmd,
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                env=_get_subprocess_env(),
                encoding="utf-8",
                errors="replace",
            )
            self._send_json(
                {"success": True, "message": "Đã xuất dữ liệu Excel thành công!"}
            )

        elif self.path == "/api/upload-nap":
            # Direct file upload endpoint from HTML file picker
            file_data_b64 = payload.get("file_data", "")
            file_name = payload.get("file_name", "uploaded.xlsx")
            if not file_data_b64:
                self._send_json(
                    {"success": False, "message": "Không có dữ liệu file!"}, status=400
                )
                return

            import base64

            temp_path = PROJECT_ROOT / "exports" / file_name
            temp_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path.write_bytes(base64.b64decode(file_data_b64))

            cmd = [
                PYTHON_EXEC,
                "-m",
                "leadhunter.presentation.cli.main",
                "nap",
                str(temp_path),
            ]
            res = subprocess.run(
                cmd,
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                env=_get_subprocess_env(),
                encoding="utf-8",
                errors="replace",
            )

            # Clean up: delete the temporary uploaded file from disk immediately
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except Exception:
                pass

            clean_msg = _clean_emoji_message(res.stdout) or "Đã nạp file thành công!"
            self._send_json({"success": True, "message": clean_msg})

        elif self.path == "/api/nap":
            file_path = payload.get("file_path", "").strip()
            cmd = [PYTHON_EXEC, "-m", "leadhunter.presentation.cli.main", "nap"]
            if file_path:
                cmd.append(file_path)
            res = subprocess.run(
                cmd,
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                env=_get_subprocess_env(),
                encoding="utf-8",
                errors="replace",
            )
            clean_msg = (
                _clean_emoji_message(res.stdout) or "Đã nạp dữ liệu Excel thành công!"
            )
            self._send_json({"success": True, "message": clean_msg})

        elif self.path == "/api/quet":
            cmd = [PYTHON_EXEC, "-m", "leadhunter.presentation.cli.main", "gop"]
            res = subprocess.run(
                cmd,
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                env=_get_subprocess_env(),
                encoding="utf-8",
                errors="replace",
            )
            self._send_json(
                {
                    "success": True,
                    "message": "Đã quét trùng và dọn dẹp cơ sở dữ liệu thành công!",
                }
            )

        elif self.path == "/api/huy":
            cmd = [PYTHON_EXEC, "-m", "leadhunter.presentation.cli.main", "rollback"]
            res = subprocess.run(
                cmd,
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                env=_get_subprocess_env(),
                encoding="utf-8",
                errors="replace",
            )
            self._send_json(
                {"success": True, "message": "Đã hoàn tác đợt cào gần nhất thành công!"}
            )

        elif self.path == "/api/reset":
            cmd = [PYTHON_EXEC, "-m", "leadhunter.presentation.cli.main", "reset-db"]
            res = subprocess.run(
                cmd,
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                env=_get_subprocess_env(),
                encoding="utf-8",
                errors="replace",
            )
            self._send_json(
                {"success": True, "message": "Đã xóa sạch cơ sở dữ liệu thành công!"}
            )

        else:
            self.send_error(404, "Unknown API")

    def _handle_get_leads(self) -> None:
        if not DB_PATH.exists():
            self._send_json({"total": 0, "excel_count": 0, "leads": []})
            return

        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT company_name, phone, address, source, status, website, score, notes FROM leads ORDER BY id DESC"
            )
            rows = cursor.fetchall()

            cursor.execute("SELECT COUNT(*) FROM leads")
            total = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM leads WHERE source='excel'")
            excel_count = cursor.fetchone()[0]

            conn.close()

            leads = [
                {
                    "company_name": r[0],
                    "phone": r[1],
                    "address": r[2],
                    "source": r[3] or "maps",
                    "status": r[4] or "NEW",
                    "website": r[5] or "",
                    "score": r[6] or 0,
                    "notes": r[7] or "",
                }
                for r in rows
            ]
            self._send_json(
                {"total": total, "excel_count": excel_count, "leads": leads}
            )
        except Exception as exc:
            self._send_json(
                {"total": 0, "excel_count": 0, "leads": [], "error": str(exc)}
            )


def start_backend_server(port: int = 5000) -> None:
    try:
        server_address = ("127.0.0.1", port)
        httpd = ThreadedHTTPServer(server_address, LeadHunterGUIHandler)
        print(
            f"🚀 Server Giao Diện LeadHunter đã sẵn sàng tại: http://127.0.0.1:{port}",
            flush=True,
        )
        sys.stdout.flush()
        httpd.serve_forever()
    except Exception as e:
        print(f"Could not start server on port {port}: {e}", flush=True)


def main() -> None:
    # Đảm bảo mã hóa UTF-8 và flush ngõ ra Terminal trên Windows
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    # 1. Khởi chạy Web Backend Server độc lập ở background thread
    server_thread = threading.Thread(
        target=start_backend_server, args=(5000,), daemon=True
    )
    server_thread.start()
    time.sleep(0.5)

    # 2. Thử bật cửa sổ pywebview Native (Chỉ trên máy có GUI như Windows)
    try:
        # Ẩn stderr tạm thời để chặn log rác GTK/QT của pywebview trên Linux
        sys_err_bak = sys.stderr
        sys.stderr = open(os.devnull, "w")
        import webview

        sys.stderr = sys_err_bak

        webview.create_window(
            title="🚀 LeadHunter Bot — Thợ Săn Lead Khách Hàng Tự Động",
            url="http://127.0.0.1:5000",
            width=1280,
            height=850,
            resizable=True,
            min_size=(900, 600),
        )
        webview.start()
    except Exception:
        # Restore stderr nếu có lỗi
        sys.stderr = sys.stdout
        # Giữ Backend Web Server tiếp tục chạy mượt mà
        try:
            while True:
                time.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            print("🛑 Đã tắt Server LeadHunter thành công.", flush=True)


if __name__ == "__main__":
    main()
