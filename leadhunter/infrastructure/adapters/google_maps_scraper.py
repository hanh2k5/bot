from __future__ import annotations
import logging

logging.getLogger("asyncio").setLevel(logging.CRITICAL)
"""Google Maps Scraper — Playwright based.

Scrapes local business listings using headless Chromium to execute JS,
simulate scrolling, and bypass standard bot detection algorithms.
"""


import logging
import time
import urllib.parse
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

from leadhunter.infrastructure.adapters.proxy_rotator import get_free_proxy
from leadhunter.domain.services.telecom_service import is_viettel, is_tong_dai


class GoogleMapsScraper:
    """Scrapes local business leads from Google Maps using Playwright or SerpApi."""

    def __init__(
        self,
        http_timeout: float = 15.0,
        proxy: dict[str, str] | None = None,
        api_key: str | None = None,
    ) -> None:
        self._timeout = http_timeout
        self._proxy = proxy
        self._api_key = api_key

    def scrape(self, keyword: str, target_count: int = 250) -> list[dict[str, str]]:
        """Scrape businesses in Ho Chi Minh City matching keyword.

        Auto-expands across HCM districts if needed until target_count leads with phone numbers are reached.

        Args:
            keyword: Industry/type of business.
            target_count: Minimum number of leads with phone numbers to collect.

        Returns:
            List of raw lead dictionaries.
        """

    def scrape_single_query(self, query: str) -> list[dict[str, str]]:
        """Scrape a single search query on Google Maps."""
        url = f"https://www.google.com/maps/search/{urllib.parse.quote(query)}"
        attempts = [("direct", None)]
        if self._proxy:
            attempts.append(("scraperapi_proxy", self._proxy))
        free = get_free_proxy()
        if free:
            attempts.append(("free_proxy", free))

        for label, proxy_cfg in attempts:
            logger.info(f"Google Maps scrape query [{label}]: {url}")
            leads = self._try_scrape(url, proxy_cfg)
            if leads:
                return leads
        return []

    def scrape_fast(
        self,
        keyword: str,
        min_clean_target: int = 80,
        status_callback=None,
        is_duplicate_fn=None,
        worker_id: int = 1,
        stop_event=None,
    ) -> list[dict[str, str]]:
        """Google Maps scraper — network-first for high yield.

        Luồng xử lý:
        1. Network RPC  → SĐT + tên gần nhất + địa chỉ đầy đủ từ payload JSON.
        2. DOM cards     → aria-label + href (place URL có tọa độ).
        3. Khi tên khớp → dùng href đầy đủ; không khớp → search URL (vẫn click được).
        """

        seen_phones: set[str] = set()

        # rpc_leads: phone → {name, address, href, website}
        rpc_leads: dict[str, dict] = {}

        # Tên rác: địa danh, quốc gia, UI text nút bấm...
        JUNK_NAMES = {
            "ho chi minh",
            "vietnam",
            "viet nam",
            "district",
            "ho chi minh city",
            "binh thanh",
            "tan binh",
            "see nearby",
            "see similar places",
            "similar places",
            "nearby cafes",
            "directions",
            "overview",
            "reviews",
            "english",
            "vietnamese",
        }
        # Quận / huyện (không phải tên quán)
        _DISTRICT_RE = re.compile(
            r"^(qu[aậ]n|qu[áa]n|ph[uư][oờ]ng|huy[eệ]n|t[hH][uị])\s*\d*$", re.IGNORECASE
        )

        UI_JUNK = {
            "restroom",
            "gender-neutral restroom",
            "paid street parking",
            "street parking",
            "parking",
            "education center",
            "training center",
            "sunday",
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "photo",
            "recycling",
            "payments",
            "claim this business",
            "debit cards",
            "open 24 hours",
            "full restoration service",
            "checks",
            "accessible entrance",
            "wheelchair",
        }

        def _is_place_id_or_junk(nm: str) -> bool:
            nm = nm.strip()
            if not nm or len(nm) < 2:
                return True
            if (
                "|" in nm
                or nm.startswith("0a")
                or nm.startswith("ChI")
                or nm.startswith("0x")
                or nm.startswith("CIH")
            ):
                return True
            if " " not in nm and len(nm) >= 7:
                has_upper = any(c.isupper() for c in nm)
                has_lower = any(c.islower() for c in nm)
                has_digit = any(c.isdigit() or c in "-_" for c in nm)
                if (has_upper and has_lower) or has_digit:
                    return True
            nm_l = nm.lower()
            if any(u in nm_l for u in UI_JUNK):
                return True
            return False

        def _extract_name(snippet: str) -> str:
            """Trích tên doanh nghiệp từ snippet RPC (chuỗi chữ hoa đầu gần SĐT)."""
            name_m = re.findall(
                r'"([A-ZÀÁẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÈÉẺẼẸÊẾỀỂỄỆÌÍỈĨỊÒÓỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÙÚỦŨỤƯỨỪỬỮỰỲÝỶỸỴĐ][^"]{3,50})"',
                snippet,
            )
            for nm in name_m:
                nm = nm.strip()
                if _is_place_id_or_junk(nm):
                    continue
                if any(j in nm.lower() for j in JUNK_NAMES):
                    continue
                if _DISTRICT_RE.match(nm):
                    continue
                if len(nm) > 4:
                    return nm
            return ""

        def _extract_address(snippet: str) -> str:
            """Trích xuất ĐỘNG 100% địa chỉ nguyên bản của bất kỳ cơ sở nào trên Google Maps (Không hardcode tên đường)."""
            # 1. Bắt chuỗi địa chỉ nguyên bản đầy đủ số nhà + đường + quận + HCM / Vietnam
            addr_m = re.findall(
                r'"(\d+[^"]{5,150}(?:Hồ Chí Minh|Ho Chi Minh|HCM|Đồng Nai|Dong Nai|Biên Hòa|Bình Dương|Vietnam|Việt Nam)[^"]{0,30})"',
                snippet,
            )
            for a in addr_m:
                a_clean = a.strip()
                if (
                    "http" not in a_clean
                    and "google.com" not in a_clean
                    and not a_clean.startswith("0a")
                ):
                    return a_clean

            # 2. Bắt chuỗi địa chỉ tổng quát có chứa HCM / Vietnam
            addr_m2 = re.findall(
                r'"([^"]{8,150}(?:Hồ Chí Minh|Ho Chi Minh|HCM|Đồng Nai|Dong Nai|Biên Hòa|Bình Dương|Vietnam|Việt Nam)[^"]{0,30})"',
                snippet,
            )
            for a in addr_m2:
                a_clean = a.strip()
                if (
                    "http" not in a_clean
                    and "google.com" not in a_clean
                    and not a_clean.startswith("0a")
                ):
                    return a_clean

            return "Việt Nam"

        def handle_response(response: Response) -> None:
            """Lắng nghe network response từ Google Maps để bắt RPC payload chứa SĐT."""
            url = response.url
            if not ("search" in url or "rpc" in url or "preview" in url):
                return
            if response.status != 200:
                return

            try:
                text = response.text()
                # Tìm tất cả SĐT di động Việt Nam (+84, 84, 03x, 05x, 07x, 08x, 09x)
                raw_matches = re.findall(
                    r"(?:\+84|84|0)\s*(?:3|5|7|8|9)\d[\d\s.\-]{7,11}\d", text
                )
                for raw in raw_matches:
                    cleaned = (
                        raw.strip()
                        .replace(" ", "")
                        .replace("-", "")
                        .replace(".", "")
                        .replace("+84", "0")
                    )
                    if cleaned.startswith("84") and len(cleaned) >= 10:
                        cleaned = "0" + cleaned[2:]
                    if len(cleaned) != 10 or not cleaned.startswith(
                        ("03", "05", "07", "08", "09")
                    ):
                        continue

                    idx = text.find(raw)
                    snippet = text[max(0, idx - 1200) : min(len(text), idx + 1200)]

                    name = _extract_name(snippet)
                    address = _extract_address(snippet)

                    rpc_leads[cleaned] = {
                        "name": name or f"__no_name_{cleaned}",
                        "address": address,
                        "href": "",
                        "website": "",
                    }
            except Exception:
                pass

        # JS trích xuất tức thì 100% dữ liệu từ thẻ danh sách trên Google Maps (Không bị đơ, không bị treo)
        CARDS_EXTRACT_JS = r"""() => {
            const out = [];
            document.querySelectorAll('div[role="feed"] > div').forEach(item => {
                const a = item.querySelector('a.hfpxzc, a.HFpxzc');
                if (!a) return;
                const name = (a.getAttribute('aria-label') || '').trim();
                const href = a.getAttribute('href') || '';
                if (!name || !href || !href.includes('/maps/place/')) return;

                // Trích xuất trang web THỰC TẾ (Không phải đường link Google internal)
                let website = '';
                const webBtn = item.querySelector('a[data-value*="Website"], a[aria-label*="Website"], a[aria-label*="Trang web"]');
                if (webBtn) {
                    const h = webBtn.href || '';
                    if (h.startsWith('http')) {
                        website = h;
                    }
                }

                // Trích xuất ĐỘNG 100% địa chỉ từ thẻ Google Maps (Không hardcode tên đường)
                let address = '';
                let phone = '';
                const text = item.innerText || '';
                const lines = text.split('\\n');
                for (let i = 0; i < lines.length; i++) {
                    const l = lines[i].trim();
                    // Ưu tiên dòng địa chỉ chứa dấu phẩy hoặc số nhà và địa danh
                    if (!address && l.length >= 6 && l !== name && !l.includes('·') && !l.includes('★') && !l.includes('Open') && !l.includes('Closed') && (l.includes(',') || /\\d/.test(l)) && (l.includes('Hồ Chí Minh') || l.includes('Ho Chi Minh') || l.includes('HCM') || l.includes('Đồng Nai') || l.includes('Dong Nai') || l.includes('Biên Hòa') || l.includes('Bình Dương') || l.includes('Vietnam') || l.includes('Việt Nam') || l.includes('Quận') || l.includes('Phường') || l.includes('Đường'))) {
                        address = l;
                    }
                    const m = l.match(/(?:\+84|84|0)\s*(?:3|5|7|8|9)\d[\d\s.\-]{7,11}\d/);
                    if (!phone && m) {
                        phone = m[0];
                    }
                }
                if (!address) {
                    for (let i = 0; i < lines.length; i++) {
                        const l = lines[i].trim();
                        if (!address && l.length >= 8 && l !== name && !l.includes('·') && !l.includes('★') && (l.includes('Hồ Chí Minh') || l.includes('Ho Chi Minh') || l.includes('HCM') || l.includes('Đồng Nai') || l.includes('Dong Nai') || l.includes('Biên Hòa') || l.includes('Bình Dương') || l.includes('Vietnam') || l.includes('Việt Nam'))) {
                            address = l;
                        }
                    }
                }
                out.push({ name, href, website, address, phone });
            });
            return out;
        }"""

        all_leads: list[dict[str, str]] = []
        seen_hrefs: set[str] = set()

        def _is_clean_phone(p_str: str) -> tuple[bool, str]:
            cleaned = (
                p_str.strip()
                .replace(" ", "")
                .replace("-", "")
                .replace(".", "")
                .replace("+84", "0")
            )
            if cleaned.startswith("84") and len(cleaned) >= 10:
                cleaned = "0" + cleaned[2:]
            if is_tong_dai(cleaned):
                return False, ""
            if is_viettel(cleaned):
                return False, ""
            return True, cleaned

        def _is_professional_website(url: str) -> bool:
            if not url or ("http://" not in url and "https://" not in url):
                return False
            allowed_links = [
                # Mạng xã hội & Sàn TMĐT
                "google.com",
                "facebook.com",
                "zalo.me",
                "tiktok.com",
                "youtube.com",
                "shopee.vn",
                "lazada.vn",
                "chotot.com",
                "instagram.com",
                "gg.gg",
                "blogspot.com",
                "kiotvietweb.vn",
                # Trang danh bạ doanh nghiệp, mã số thuế (Thêm mới)
                "hosocongty.vn",
                "hosocongty.com",
                "masothue.com",
                "masothue.vn",
                "trangvangvietnam.com",
                "bizz.vn",
                "hosodoanhnghiep.vn",
                "fact-link.com",
                "thongtindoanhnghiep.co",
                "bizs.vn",
                # Food delivery & Aggregators
                "foody.vn",
                "shopeefood.vn",
                "now.vn",
                "diadiemanuong.com",
                "easysalon.vn",
                "pasgo.vn",
                "riviu.vn",
                "loship.vn",
            ]
            for domain in allowed_links:
                if domain in url:
                    return False
            return True

        try:
            # 3 Brains (Môi trường mạng)
            proxy_playwright = None
            brain_name = "Mạng gốc (Hệ Free)"

            # Cấu hình user-agent tương ứng với từng tên nhân
            user_agents = {
                1: "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                2: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                3: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            }

            # Xoay vòng lấy tên nhân từ mảng tùy ý và gán user-agent tương ứng
            os_names = ["Linux", "Mac", "Win"]
            os_name = os_names[(worker_id - 1) % len(os_names)]
            ua_string = user_agents.get(worker_id, user_agents[1])

            with sync_playwright() as p:
                launch_kwargs = {
                    "headless": True,
                    "args": ["--no-sandbox", "--disable-setuid-sandbox"],
                }
                if proxy_playwright:
                    launch_kwargs["proxy"] = proxy_playwright

                browser = p.chromium.launch(**launch_kwargs)
                context = browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    user_agent=ua_string,
                    locale="vi-VN",
                )
                context.route(
                    "**/*.{png,jpg,jpeg,gif,svg,webp,woff,woff2,ttf,otf}",
                    lambda r: r.abort(),
                )
                page = context.new_page()
                page.on("response", handle_response)

                # Scrape directly with the exact keyword provided
                url = f"https://www.google.com/maps/search/{urllib.parse.quote(keyword)}?hl=vi"

                try:
                    try:
                        # Tăng timeout lên 15s để tránh nghẽn khi chạy 3 luồng
                        page.goto(url, wait_until="domcontentloaded", timeout=15000)
                    except Exception:
                        # Đợi thêm một chút nếu bị timeout nhưng trang vẫn đang load
                        page.wait_for_load_state("domcontentloaded", timeout=5000)
                        pass

                    try:
                        feed = page.query_selector("div[role='feed']")
                        if not feed:
                            # Nếu không có feed, thử đợi thêm một chút
                            try:
                                page.wait_for_selector("div[role='feed']", timeout=3000)
                                feed = page.query_selector("div[role='feed']")
                            except Exception:
                                pass

                        if feed:
                            # Cuộn feed xuống cuối 3 lần cho mỗi batch để khởi động list
                            for _ in range(3):
                                feed.evaluate("el => el.scrollTop = el.scrollHeight")
                                time.sleep(0.3)
                    except Exception:
                        pass

                    last_count = 0
                    stuck_count = 0

                    # Cuộn liên tục để trigger RPC payload
                    for _ in range(50):
                        if stop_event and stop_event.is_set():
                            break
                        if len(all_leads) >= min_clean_target:
                            break

                        # Dùng JS lấy dữ liệu cực nhanh không sợ đơ
                        cards = page.evaluate(CARDS_EXTRACT_JS)

                        # Tự động click vào các quán có trong DOM để load detail
                        for i, c in enumerate(cards):
                            if stop_event and stop_event.is_set():
                                break
                            if c["href"] not in seen_hrefs:
                                seen_hrefs.add(c["href"])
                                try:
                                    # Click the actual card to trigger detail panel & RPC
                                    els = page.query_selector_all("a.hfpxzc, a.HFpxzc")
                                    if i < len(els):
                                        els[i].click(force=True, timeout=1000)
                                        time.sleep(0.8)
                                except Exception:
                                    pass

                        # Kiểm tra xem có lấy được thêm dữ liệu không
                        if len(rpc_leads) > last_count:
                            last_count = len(rpc_leads)
                            stuck_count = 0
                        else:
                            stuck_count += 1
                            if stuck_count > 6:
                                # Cuộn đến cuối mà không có thẻ mới
                                print(
                                    "  ✅ [Đã cuộn đến cuối danh sách Google Maps]",
                                    flush=True,
                                )
                                break

                        # Thực hiện cuộn xuống
                        try:
                            page.mouse.wheel(0, 4000)
                            page.evaluate(
                                """() => {
                                const feed = document.querySelector('div[role="feed"]');
                                if(feed) feed.scrollBy(0, 10000);
                                window.scrollBy(0, 10000);
                            }"""
                            )
                        except Exception:
                            pass
                        time.sleep(1.0)

                    # Kết thúc cuộn, bắt đầu kiểm tra và lọc dữ liệu
                    if status_callback:
                        status_callback(
                            f"🔄 [ {os_name}] Đang trích xuất chi tiết {len(seen_hrefs)} địa điểm...",
                            -1,
                        )
                    else:
                        print(
                            f"  🔄 [ {os_name}] Đang trích xuất chi tiết {len(seen_hrefs)} địa điểm...",
                            flush=True,
                        )

                    for place_url in seen_hrefs:
                        if stop_event and stop_event.is_set():
                            break
                        if len(all_leads) >= min_clean_target:
                            break

                        # Tìm thông tin thẻ cơ bản tương ứng với URL
                        card_info = next(
                            (c for c in cards if c["href"] == place_url), None
                        )
                        if not card_info:
                            continue

                        place_name = card_info["name"]
                        if not place_name:
                            continue

                        # Loại bỏ các chuỗi rác
                        if _is_place_id_or_junk(place_name):
                            continue
                        if any(j in place_name.lower() for j in JUNK_NAMES):
                            continue
                        if _DISTRICT_RE.match(place_name):
                            continue

                        place_addr = card_info["address"]
                        place_phone = card_info["phone"]
                        place_web = card_info["website"]

                        # Check duplicate theo tên (tránh gọi nhiều lần hàm _is_duplicate_fn)
                        if is_duplicate_fn and is_duplicate_fn(place_phone, place_name):
                            if status_callback:
                                status_callback(
                                    f"❌ [ {os_name}] Bỏ qua: {place_name[:30]} (Trùng lặp)",
                                    len(all_leads),
                                )
                            else:
                                print(
                                    f"  ❌ [ {os_name}] Bỏ qua: {place_name[:30]} (Trùng lặp)",
                                    flush=True,
                                )
                            continue

                        p_str = place_phone
                        if not p_str or not place_addr or len(place_addr) < 15:
                            # Trực tiếp mở URL trang cơ sở để trích xuất 100% SĐT, Địa chỉ chi tiết có số nhà, Tên và Website
                            d_page = None
                            try:
                                d_page = context.new_page()
                                d_page.goto(
                                    place_url,
                                    wait_until="domcontentloaded",
                                    timeout=6000,
                                )
                                try:
                                    d_page.wait_for_selector(
                                        "h1.DUwfe, h1", timeout=3000
                                    )
                                    # Wait specifically for the phone button if we don't have phone
                                    if not place_phone:
                                        d_page.wait_for_selector(
                                            'button[data-item-id*="phone"]',
                                            timeout=1500,
                                        )
                                except Exception:
                                    pass
                                time.sleep(1.2)
                                detail = d_page.evaluate(
                                    """() => {
                                    const h1 = document.querySelector('h1.DUwfe, h1');
                                    const addrBtn = document.querySelector('button[data-item-id="address"]');
                                    const phoneBtn = document.querySelector('button[data-item-id*="phone"]');
                                    const webBtn = document.querySelector('a[data-item-id="authority"]');
                                    return {
                                        name: h1 ? h1.innerText.trim() : '',
                                        address: addrBtn ? addrBtn.innerText.replace(/^[\\s\\S]*?\\n/, '').trim() : '',
                                        phone: phoneBtn ? phoneBtn.innerText.replace(/^[\\s\\S]*?\\n/, '').trim() : '',
                                        website: webBtn ? (webBtn.href || '') : ''
                                    };
                                }"""
                                )
                                if detail.get("phone"):
                                    p_str = detail["phone"]
                                if detail.get("address") and len(
                                    detail["address"]
                                ) > len(place_addr):
                                    place_addr = detail["address"]
                                if detail.get("name") and len(detail["name"]) > len(
                                    place_name
                                ):
                                    place_name = detail["name"]
                                if detail.get("website"):
                                    place_web = detail["website"]
                            except Exception:
                                pass
                            finally:
                                if d_page:
                                    try:
                                        d_page.close()
                                    except Exception:
                                        pass

                        if not p_str:
                            # Ghép SĐT từ RPC leads dựa vào Name hoặc Address để tránh gán nhầm
                            for ph, info in list(rpc_leads.items()):
                                if ph in seen_phones:
                                    continue
                                if info["name"] and (
                                    info["name"].lower() in place_name.lower()
                                    or place_name.lower() in info["name"].lower()
                                ):
                                    p_str = ph
                                    break
                                if (
                                    info["address"]
                                    and place_addr
                                    and (
                                        info["address"].lower() in place_addr.lower()
                                        or place_addr.lower() in info["address"].lower()
                                    )
                                ):
                                    p_str = ph
                                    break

                        # BẮT BUỘC BỎ QUA NẾU ĐƠN VỊ CÓ WEBSITE THỰC TẾ (co web bo qua)
                        if _is_professional_website(place_web):
                            if status_callback:
                                status_callback(
                                    f"🚫 [ {os_name}] Bỏ qua: {place_name[:30]} (Có Web)",
                                    len(all_leads),
                                )
                            else:
                                print(
                                    f"  🚫 [ {os_name}] [Bỏ qua - Có Web]: {place_name[:30]} ({place_web[:20]}...)",
                                    flush=True,
                                )
                            continue

                        if not p_str:
                            if status_callback:
                                status_callback(
                                    f"⏳ [ {os_name}] Bỏ qua: {place_name[:30]} (Chưa có SĐT)",
                                    len(all_leads),
                                )
                            else:
                                print(
                                    f"  ⏳ [ {os_name}] [Chưa có SĐT]: {place_name[:30]}",
                                    flush=True,
                                )
                            continue

                        # BẮT BUỘC BỎ QUA NẾU LÀ TỔNG ĐÀI / MÁY BÀN
                        ok, clean_p = _is_clean_phone(p_str)
                        if not ok:
                            if status_callback:
                                status_callback(
                                    f"⏭️ [ {os_name}] Bỏ qua: {place_name[:30]} (Số bàn {p_str})",
                                    len(all_leads),
                                )
                            else:
                                print(
                                    f"  ⏭️ [ {os_name}] [Bỏ qua - Số bàn {p_str}]: {place_name[:30]}",
                                    flush=True,
                                )
                            continue

                        if clean_p in seen_phones:
                            continue

                        seen_phones.add(clean_p)

                        all_leads.append(
                            {
                                "company_name": place_name,
                                "contact_name": "",
                                "email": "",
                                "phone": clean_p,
                                "website": "",
                                "address": place_addr,
                                "source": "",
                                "source_reference": place_url,
                            }
                        )

                        if status_callback:
                            status_callback(
                                f"🔎 [ {os_name}] {place_name[:25]} | {clean_p}",
                                -1,
                            )
                        else:
                            print(
                                f"  🔎 [ {os_name}] [ĐÃ TÌM THẤY LEAD] {place_name} | {clean_p}",
                                flush=True,
                            )

                except Exception as exc:
                    pass

                browser.close()

        except Exception as exc:
            pass

        logger.info(f"scrape_fast hoàn thành: {len(all_leads)} leads thô")
        return all_leads

    def scrape(self, keyword: str, target_count: int = 400) -> list[dict[str, str]]:

        districts = ["Hồ Chí Minh", "Bình Dương"]
        all_leads: list[dict[str, str]] = []
        seen_names: set[str] = set()

        for district in districts:
            query = f"{keyword} {district}".strip()
            url = f"https://www.google.com/maps/search/{urllib.parse.quote(query)}"

            attempts = [("direct", None)]
            if self._proxy:
                attempts.append(("scraperapi_proxy", self._proxy))
            free = get_free_proxy()
            if free:
                attempts.append(("free_proxy", free))

            for label, proxy_cfg in attempts:
                logger.info(f"Google Maps scrape attempt [{label}]: {url}")
                leads = self._try_scrape(url, proxy_cfg)
                if leads:
                    for lead in leads:
                        name_key = lead["company_name"].strip().lower()
                        if name_key not in seen_names:
                            seen_names.add(name_key)
                            all_leads.append(lead)

                    phone_count = sum(1 for l in all_leads if l.get("phone"))
                    logger.info(
                        f"Collected total {len(all_leads)} leads ({phone_count} with phone)"
                    )
                    break
                logger.warning(
                    f"Google Maps [{label}] returned 0 results, trying next…"
                )

            phone_count = sum(1 for l in all_leads if l.get("phone"))
            if phone_count >= target_count:
                logger.info(f"Target count reached ({phone_count}/{target_count})")
                break

        return all_leads

    def _try_scrape(self, url: str, proxy_cfg: dict | None) -> list[dict[str, str]]:
        """Single scrape attempt with optional proxy. Clicks each listing for details."""
        try:
            with sync_playwright() as p:
                launch_args = {
                    "headless": True,
                    "args": ["--no-sandbox", "--disable-setuid-sandbox"],
                }
                if proxy_cfg:
                    launch_args["proxy"] = proxy_cfg

                browser = p.chromium.launch(**launch_args)
                context = browser.new_context(
                    ignore_https_errors=True,
                    viewport={"width": 1280, "height": 800},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                )
                # Block heavy media & fonts to accelerate page loads 3x
                context.route(
                    "**/*.{png,jpg,jpeg,gif,svg,webp,woff,woff2,ttf,otf}",
                    lambda route: route.abort(),
                )

                page = context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=45000)

                page.wait_for_selector("div[role='feed']", timeout=15000)

                # Fast scroll to load results
                for _ in range(15):
                    page.hover("div[role='feed']")
                    page.mouse.wheel(0, 10000)
                    time.sleep(0.15)

                # Collect all listing info from feed links
                listing_links = page.query_selector_all(
                    "a.hfpxzc"
                ) or page.query_selector_all("a.HFpxzc")
                items = []
                for link in listing_links:
                    name = link.get_attribute("aria-label") or ""
                    href = link.get_attribute("href") or ""
                    if name and href:
                        items.append({"name": name, "href": href})

                leads = []
                logger.info(
                    f"Found {len(items)} listing links, ultra-fast extracting details..."
                )

                for i, item in enumerate(items[:150]):
                    try:
                        page.goto(
                            item["href"], wait_until="domcontentloaded", timeout=15000
                        )
                        time.sleep(0.15)

                        name = item["name"]
                        phone = ""
                        website = ""
                        address = "TP. Hồ Chí Minh"

                        # Extract phone from detail panel
                        phone_btn = page.query_selector(
                            "button[data-tooltip='Copy phone number']"
                        )
                        if not phone_btn:
                            phone_btn = page.query_selector(
                                "button[aria-label*='Phone']"
                            )
                        if not phone_btn:
                            phone_elements = page.query_selector_all(
                                "button[data-item-id*='phone']"
                            )
                            if phone_elements:
                                phone_btn = phone_elements[0]

                        if phone_btn:
                            phone_text = (
                                phone_btn.get_attribute("aria-label")
                                or phone_btn.inner_text()
                            )
                            phone_match = re.search(
                                r"((?:\+84|0)[\d\s\-\.]{8,14})", phone_text
                            )
                            if phone_match:
                                phone = re.sub(r"[\s\-\.]", "", phone_match.group(1))

                        # Extract website
                        web_btn = page.query_selector("a[data-item-id='authority']")
                        if web_btn:
                            website = web_btn.get_attribute("href") or ""

                        # Extract address
                        addr_btn = page.query_selector("button[data-item-id='address']")
                        if addr_btn:
                            addr_text = (
                                addr_btn.get_attribute("aria-label")
                                or addr_btn.inner_text()
                            )
                            addr_text = re.sub(
                                r"^(Address|Địa chỉ):\s*",
                                "",
                                addr_text,
                                flags=re.IGNORECASE,
                            )
                            addr_text = re.sub(
                                r"[\ue000-\uefff]", "", addr_text
                            ).strip()
                            if addr_text:
                                address = addr_text

                        leads.append(
                            {
                                "company_name": name,
                                "contact_name": "",
                                "email": "",
                                "phone": phone,
                                "website": website,
                                "address": address,
                                "source": "google_maps",
                                "source_reference": item["href"],
                            }
                        )

                        if phone:
                            logger.info(
                                f"  [{i+1}/{len(items)}] {name} | phone={phone}"
                            )

                    except Exception as exc:
                        logger.debug(f"Error extracting listing {i}: {exc}")
                        continue

                browser.close()
                return leads
        except Exception as exc:
            logger.warning(f"Scrape attempt failed: {exc}")
            return []

    def _parse_html(self, html: str, source_url: str) -> list[dict[str, str]]:
        soup = BeautifulSoup(html, "html.parser")
        leads: list[dict[str, str]] = []

        # Primary: use a.hfpxzc links (current Google Maps 2025+ structure)
        links = soup.select("a.hfpxzc") or soup.select("a.HFpxzc")
        if not links:
            logger.warning("No business listing links found in Maps HTML")
            return leads

        for link in links:
            try:
                name = link.get("aria-label", "")
                if not name:
                    continue

                href = link.get("href", source_url)

                # Find sibling/parent W4Efsd elements for address details
                address = "TP. Hồ Chí Minh"
                phone = ""
                parent = link.find_parent()

                if parent:
                    detail_divs = parent.select("div.W4Efsd")
                    full_text = " | ".join(
                        d.get_text(" ", strip=True) for d in detail_divs
                    )

                    # Extract phone
                    phone_match = re.search(
                        r"((?:\+84|0)[\d\s\-]{8,12})", full_text.replace("-", "")
                    )
                    if phone_match:
                        phone = re.sub(r"[\s\-]", "", phone_match.group(1))

                    # Extract address from W4Efsd text parts
                    for d in detail_divs:
                        text = d.get_text(" ", strip=True)
                        # Look for Vietnamese address patterns
                        if any(
                            x in text.lower()
                            for x in [
                                "đ.",
                                "đường",
                                "phường",
                                "quận",
                                "tân",
                                "bình",
                                "gò vấp",
                            ]
                        ):
                            # Clean up: remove category prefix like "Spa · "
                            parts = text.split("·")
                            for part in parts:
                                part = part.strip()
                                if any(c.isdigit() for c in part) or any(
                                    x in part.lower()
                                    for x in ["đ.", "đường", "phường", "quận"]
                                ):
                                    street = part.strip()
                                    # Always append HCM since query is scoped to HCM
                                    address = f"{street}, TP. Hồ Chí Minh"
                                    break

                leads.append(
                    {
                        "company_name": name,
                        "contact_name": "",
                        "email": "",
                        "phone": phone,
                        "website": "",
                        "address": address,
                        "source": "google_maps",
                        "source_reference": href,
                    }
                )
            except Exception:
                continue

        return leads

    def _scrape_via_serpapi(self, keyword: str) -> list[dict[str, str]]:
        logger.info(f"Querying SerpApi for Google Maps: keyword={keyword}")
        leads = []
        try:
            import requests

            url = "https://serpapi.com/search.json"
            params = {
                "engine": "google_maps",
                "q": f"{keyword} Ho Chi Minh",
                "api_key": self._api_key,
            }
            res = requests.get(url, params=params, timeout=self._timeout)
            res.raise_for_status()
            data = res.json()
            local_results = data.get("local_results", [])
            for item in local_results:
                leads.append(
                    {
                        "company_name": item.get("title", ""),
                        "contact_name": "",
                        "email": "",
                        "phone": item.get("phone", ""),
                        "website": item.get("website", ""),
                        "address": item.get("address", "TP. Hồ Chí Minh"),
                        "source": "google_maps",
                        "source_reference": item.get("link", ""),
                    }
                )
        except Exception as exc:
            logger.error(f"SerpApi Google Maps scrape failed: {exc}", exc_info=True)
        return leads


import re
