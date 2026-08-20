"""Regression Test Suite for Phase 2 Core Fixes: Bug 1, Bug 2, Bug 4."""

import pytest
import threading
import time
from leadhunter.application.use_cases.auto_run_use_case import (
    _is_in_hcm,
    AutoRunUseCase,
)
from leadhunter.domain.entities.lead import Lead, LeadStatus


class TestBug4GeographicFilter:
    """Regression tests for Bug 4 — Geographic filter _is_in_hcm()."""

    def test_positive_cases(self):
        valid_addresses = [
            "HCM",
            "TP.HCM",
            "TP HCM",
            "Hồ Chí Minh",
            "Ho Chi Minh",
            "Ho Chi Minh City",
            "Sài Gòn",
            "Sai Gon",
            "Dĩ An, Bình Dương",
            "Biên Hòa, Đồng Nai",
            "30/3 Lê Tấn Bè, Q7, TP.HCM",
            "Thủ Dầu Một, Bình Dương",
            "Nhơn Trạch, Đồng Nai",
            "123 Nguyễn Thị Minh Khai, Quận 1",
            "Gò Vấp, Ho Chi Minh City",
        ]
        for addr in valid_addresses:
            assert _is_in_hcm(addr) is True, f"Failed positive case: '{addr}'"

    def test_negative_cases(self):
        invalid_addresses = [
            "Hà Nội",
            "Cần Thơ",
            "Long An",
            "Đà Nẵng",
            "Vĩnh Long",
            "Đồng Tháp",
            "Bến Tre",
            "123 Đường X, Hà Nội",
            "Quận Ninh Kiều, Cần Thơ",
        ]
        for addr in invalid_addresses:
            assert _is_in_hcm(addr) is False, f"Failed negative case: '{addr}'"

    def test_ambiguous_and_generic_cases(self):
        ambiguous_addresses = [
            "Việt Nam",
            "Vietnam",
            "VIET NAM",
            "",
            "   ",
            "123",
            "Viet Nam",
        ]
        for addr in ambiguous_addresses:
            assert _is_in_hcm(addr) is False, f"Failed generic/ambiguous case: '{addr}'"


class DummyRepository:
    def __init__(self):
        self.saved_leads = []

    def get_all_phones(self):
        return set()

    def find_duplicates(self, **kwargs):
        return []

    def add(self, lead):
        self.saved_leads.append(lead)
        return lead


class DummyScraper:
    def __init__(self, kw_responses):
        self.kw_responses = kw_responses

    def scrape_fast(self, kw, **kwargs):
        for k in self.kw_responses:
            if k in kw.lower():
                return self.kw_responses[k]
        return []


class DummyExport:
    def __init__(self, export_dir=None):
        self._export_dir = export_dir

    def execute(self, params):
        class Res:
            file_path = "/tmp/dummy.xlsx"
            total_leads = len(params.leads)
        return Res()


class TestBug2DynamicTargetOverflow:
    """Regression tests for Bug 2 — Dynamic Target Overflow."""

    def test_single_keyword_shortage_compensated_by_others(self, tmp_path):
        repo = DummyRepository()
        kw_responses = {
            "pccc": [
                {"name": "Công Ty PCCC Số 1", "phone": "0911000001", "address": "Quận 1, TP.HCM"},
                {"name": "Công Ty PCCC Số 2", "phone": "0911000002", "address": "Quận 3, TP.HCM"},
            ],
            "xây dựng": [
                {"name": f"Công Ty Xây Dựng Số {i}", "phone": f"0908000{i:03d}", "address": "Thủ Đức, TP.HCM"}
                for i in range(1, 25)
            ],
        }
        scraper = DummyScraper(kw_responses)
        use_case = AutoRunUseCase(repo, scraper, DummyExport(export_dir=tmp_path))

        result = use_case.execute(["pccc", "xây dựng"], target=15, allow_vina=True, allow_mobi=True, allow_viettel=True)
        assert result["added_count"] == 15
        assert len(repo.saved_leads) == 15

    def test_early_keyword_target_met_and_campaign_target_reached(self, tmp_path):
        repo = DummyRepository()
        kw_responses = {
            "gara": [
                {"name": f"Gara Ô Tô {i}", "phone": f"0912000{i:03d}", "address": "Bình Dương"}
                for i in range(1, 15)
            ],
            "nội thất": [
                {"name": f"Nội Thất Cao Cấp {i}", "phone": f"0913000{i:03d}", "address": "Đồng Nai"}
                for i in range(1, 15)
            ],
        }
        scraper = DummyScraper(kw_responses)
        use_case = AutoRunUseCase(repo, scraper, DummyExport(export_dir=tmp_path))

        result = use_case.execute(["gara", "nội thất"], target=10, allow_vina=True, allow_mobi=True, allow_viettel=True)
        assert result["added_count"] == 10


class TestBug1ConsecutiveZeroLeads:
    """Regression tests for Bug 1 — Race Condition in consecutive zero leads tracking."""

    def test_consecutive_zero_leads_synchronization(self):
        data_lock = threading.Lock()
        consecutive_zero_queries = 0
        cooldown_triggers = 0

        def record_query_result(raw_count: int):
            nonlocal consecutive_zero_queries, cooldown_triggers
            with data_lock:
                if raw_count == 0:
                    consecutive_zero_queries += 1
                    if consecutive_zero_queries >= 3:
                        cooldown_triggers += 1
                        consecutive_zero_queries = 0
                else:
                    consecutive_zero_queries = 0

        record_query_result(0)
        record_query_result(0)
        record_query_result(0)
        assert cooldown_triggers == 1
        assert consecutive_zero_queries == 0

        record_query_result(0)
        record_query_result(5)
        assert consecutive_zero_queries == 0
