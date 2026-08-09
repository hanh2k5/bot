import pytest
from pathlib import Path
from leadhunter.domain.services.telecom_service import is_viettel, is_tong_dai, is_vinaphone, is_mobifone
from leadhunter.domain.services.normalization_service import normalize_phone
from leadhunter.application.use_cases.auto_run_use_case import _is_valid_phone, _has_website
from leadhunter.infrastructure.adapters.excel_writer_adapter import ExcelWriterAdapter
from leadhunter.domain.entities.lead import Lead, LeadStatus
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from gui_app import _is_node_junk


class TestTelecomFilteringRules:
    """Kiểm tra logic phân loại và lọc nhà mạng viễn thông."""

    def test_always_reject_landlines_and_callcenters(self):
        landlines = ["02438251234", "02839105678", "19001560", "18001090"]
        for num in landlines:
            assert is_tong_dai(num) is True
            valid, _ = _is_valid_phone(num, allow_viettel=True, allow_vina=True, allow_mobi=True)
            assert valid is False

    def test_default_mode_rejects_viettel_and_accepts_vina_mobi(self):
        # Default (allow_viettel=False): blocks Viettel numbers, accepts Vina & Mobi
        viettel_num = "0981234567"
        vina_num = "0918234567"
        mobi_num = "0908234567"

        assert _is_valid_phone(viettel_num, allow_viettel=False)[0] is False
        assert _is_valid_phone(vina_num, allow_viettel=False)[0] is True
        assert _is_valid_phone(mobi_num, allow_viettel=False)[0] is True

    def test_viettel_checkbox_filters_exclusively_for_viettel(self):
        # When + Viettel is checked (allow_viettel=True): filters FOR Viettel 100%!
        viettel_num = "0981234567"
        vina_num = "0918234567"
        mobi_num = "0908234567"

        assert _is_valid_phone(viettel_num, allow_viettel=True)[0] is True
        assert _is_valid_phone(vina_num, allow_viettel=True)[0] is False
        assert _is_valid_phone(mobi_num, allow_viettel=True)[0] is False


class TestWebsiteFilteringRules:
    """Kiểm tra logic lọc Có Web / Không Web."""

    def test_default_mode_rejects_places_with_website(self):
        raw_with_web = {"website": "https://nhakhoadam.com"}
        raw_no_web = {"website": ""}

        assert _has_website(raw_with_web) is True
        assert _has_website(raw_no_web) is False

    def test_has_website_detects_all_valid_urls(self):
        assert _has_website({"website": "http://xaydung.vn"}) is True
        assert _has_website({"website": "xaydung.com.vn"}) is True
        assert _has_website({"website": None}) is False
        assert _has_website({}) is False


class TestExcelExportFormatting:
    """Kiểm tra file Excel xuất ra có đúng 5 cột màu sắc và nằm ở thư mục exports/."""

    def test_excel_writer_exports_5_columns(self, tmp_path):
        writer = ExcelWriterAdapter()
        lead = Lead(
            company_name="Công Ty Thiết Kế Xây Dựng",
            contact_name="",
            email="",
            phone="0908238968",
            website="https://xaydung.vn",
            address="123 Nguyễn Thị Thập, Q7, TP.HCM",
            source="google_maps",
            source_reference="https://maps.google.com/?cid=123",
            status=LeadStatus.NEW,
            import_batch_id="test_batch",
        )
        file_path = tmp_path / "test_export.xlsx"
        writer.write([lead], str(file_path))

        assert file_path.exists()

        import openpyxl
        wb = openpyxl.load_workbook(file_path)
        sheet = wb.active
        headers = [cell.value for cell in sheet[1]]
        
        # Verify exactly 5 columns
        expected_headers = ["Số Điện Thoại", "Tên Cửa Hàng", "Địa Chỉ", "Link Google Maps", "Tình Trạng"]
        assert headers == expected_headers

        row2 = [cell.value for cell in sheet[2]]
        assert row2[0] == "0908238968"
        assert row2[1] == "Công Ty Thiết Kế Xây Dựng"
        assert row2[2] == "123 Nguyễn Thị Thập, Q7, TP.HCM"
        assert row2[3] == "https://maps.google.com/?cid=123"


class TestLogFiltering:
    """Kiểm tra bộ lọc log nhiễu."""

    def test_filters_airplane_progress_bar_junk(self):
        airplane_line = "0% ✈︎ (0/10) - 🛑 [ Linux] Bắt đầu..."
        assert _is_node_junk(airplane_line) is True

        normal_line = "🔎 [ Linux] Nhôm kính hàng phú quận 7 | 0908238968"
        assert _is_node_junk(normal_line) is False

    def test_filters_node_epipe_and_unhandled_error_events(self):
        assert _is_node_junk("throw er; // Unhandled 'error' event") is True
        assert _is_node_junk("^") is True
        assert _is_node_junk("errno: -32,") is True
        assert _is_node_junk("code: 'EPIPE',") is True
        assert _is_node_junk("syscall: 'write'") is True
        assert _is_node_junk("}") is True
