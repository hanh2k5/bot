"""Unit tests for AutoRunUseCase (smart filters)."""

from __future__ import annotations

from unittest.mock import MagicMock, call

from leadhunter.application.use_cases.auto_run_use_case import AutoRunUseCase
from leadhunter.application.dtos import ExportResultDTO


def test_auto_run_filters_correctly(tmp_path) -> None:
    # 1. Setup mock repository and scrapers
    repo = MagicMock()
    repo.find_duplicates.return_value = []

    maps_scraper = MagicMock()

    # Trả về 5 items ở lần gọi đầu tiên, còn lại trả về [] để dừng sớm
    good_items = [
        {
            "company_name": "Nha Khoa A",
            "phone": "0981112222",  # Viettel → skip
            "website": "https://has-web.com",  # Has web → skip
            "address": "123 Nguyễn Huệ, Quận 1, Hồ Chí Minh 70000",
            "source": "google_maps"
        },
        {
            "company_name": "Nha Khoa B",
            "phone": "0912223333",  # Vina (valid)
            "website": "",
            "address": "45 Hoàn Kiếm, Hà Nội",  # Ngoài HCM → skip
            "source": "google_maps"
        },
        {
            "company_name": "Nha Khoa C",
            "phone": "0904445555",  # Mobi (valid) → OK
            "website": "",
            "address": "76 Phan Đăng Lưu, Bình Thạnh, Hồ Chí Minh 70000",
            "source": "google_maps"
        },
        {
            "company_name": "Nha Khoa D",
            "phone": "0968889999",  # Viettel → skip
            "website": "",
            "address": "89 Đinh Tiên Hoàng, Quận 1, Hồ Chí Minh 70000",
            "source": "google_maps"
        },
        {
            "company_name": "Nha Khoa E",
            "phone": "0917778888",  # Vina (valid) → OK
            "website": "",
            "address": "12 Cộng Hòa, Tân Bình, Hồ Chí Minh 70000",
            "source": "google_maps"
        }
    ]
    # Lần đầu trả data, các lần sau trả [] → hết dữ liệu → dừng
    maps_scraper.scrape_fast.side_effect = [good_items] + [[]] * 200

    export_use_case = MagicMock()
    export_use_case._export_dir = tmp_path
    export_use_case.execute.return_value = ExportResultDTO(
        output_file_path=str(tmp_path / "telesale_hcm_test.xlsx"),
        record_count=2,
        executed_at="2026-07-25T12:00:00Z"
    )

    use_case = AutoRunUseCase(
        repository=repo,
        maps_scraper=maps_scraper,
        export_use_case=export_use_case
    )

    from unittest.mock import patch
    with patch("time.sleep"):
        # 2. Run use case — dùng "nha khoa" để tên mock items khớp keyword filter
        result = use_case.execute(["nha khoa"])

    # 3. Verify counts
    # Valid leads: Nha Khoa C (Mobi, HCM, No Web), Nha Khoa E (Vina, HCM, No Web)
    assert result["skipped_has_website"] >= 1   # Nha Khoa A
    assert result["skipped_not_hcm"] >= 1       # Nha Khoa B
    assert result["skipped_viettel"] >= 1       # Nha Khoa D
    assert result["export_file"].endswith(".xlsx")

    # Verify repository add calls
    assert repo.add.call_count == 2
