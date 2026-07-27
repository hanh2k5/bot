"""Unit tests for AutoRunUseCase (smart filters)."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from leadhunter.application.use_cases.auto_run_use_case import AutoRunUseCase
from leadhunter.application.dtos import ExportResultDTO
from leadhunter.domain.entities.lead import LeadStatus


def test_auto_run_filters_correctly() -> None:
    # 1. Setup mock repository and scrapers
    repo = MagicMock()
    repo.find_duplicates.return_value = []
    
    maps_scraper = MagicMock()
    # Google Maps returns 3 items:
    # - 1 with website (should be skipped)
    # - 1 in Hanoi (should be skipped)
    # - 1 valid in HCM without website (should be imported)
    maps_scraper.scrape.return_value = [
        {
            "company_name": "Spa A",
            "phone": "0981112222", # Viettel, but filtered at phone step
            "website": "https://has-web.com",
            "address": "District 1, Ho Chi Minh",
            "source": "google_maps"
        },
        {
            "company_name": "Spa B",
            "phone": "0912223333", # Vina (valid)
            "website": "",
            "address": "Hoan Kiem, Ha Noi",
            "source": "google_maps"
        },
        {
            "company_name": "Spa C",
            "phone": "0904445555", # Mobi (valid)
            "website": "",
            "address": "Binh Thanh, Ho Chi Minh",
            "source": "google_maps"
        }
    ]

    fb_scraper = MagicMock()
    # Facebook scraper returns 2 items:
    # - 1 with Viettel number (should be skipped)
    # - 1 with Vina number (valid)
    fb_scraper.scrape.return_value = [
        {
            "company_name": "Spa D",
            "phone": "0968889999", # Viettel (should be skipped)
            "website": "",
            "address": "District 3, Ho Chi Minh",
            "source": "facebook"
        },
        {
            "company_name": "Spa E",
            "phone": "0917778888", # Vina (valid)
            "website": "",
            "address": "Tan Binh, Ho Chi Minh",
            "source": "facebook"
        }
    ]

    export_use_case = MagicMock()
    export_use_case.execute.return_value = ExportResultDTO(
        output_file_path="exports/telesale_hcm_test.xlsx",
        record_count=2,
        executed_at="2026-07-25T12:00:00Z"
    )

    use_case = AutoRunUseCase(
        repository=repo,
        maps_scraper=maps_scraper,
        fb_scraper=fb_scraper,
        export_use_case=export_use_case
    )

    # 2. Run use case
    result = use_case.execute(["spa"])

    # 3. Verify counts
    # Valid leads: Spa C (Mobi, HCM, No Web), Spa E (Vina, HCM, No Web)
    assert result["added_count"] == 2
    assert result["skipped_viettel"] == 1       # Spa D
    assert result["skipped_has_website"] == 1   # Spa A
    assert result["skipped_not_hcm"] == 1       # Spa B
    assert result["export_file"] == "exports/telesale_hcm_test.xlsx"

    # Verify repository add calls
    assert repo.add.call_count == 2
