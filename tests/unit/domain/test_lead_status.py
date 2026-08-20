"""Unit tests for LeadStatus and status transitions (REQ-041, AS-06)."""

import pytest

from leadhunter.domain.constants import STATUS_TRANSITIONS
from leadhunter.domain.entities.lead import LeadStatus
from leadhunter.domain.exceptions import InvalidStatusTransitionError
from leadhunter.domain.services.status_service import validate_transition


class TestLeadStatusEnum:
    """Tests for LeadStatus enum."""

    def test_all_statuses_exist(self) -> None:
        """All statuses from AS-06 are defined."""
        expected = {"NEW", "VALIDATED", "CONTACTED", "QUALIFIED", "CONVERTED", "REJECTED", "DUPLICATE"}
        actual = {s.value for s in LeadStatus}
        assert expected == actual

    def test_lead_status_is_string_comparable(self) -> None:
        """LeadStatus values can be compared to strings."""
        assert LeadStatus.NEW.value == "NEW"
        assert LeadStatus("NEW") == LeadStatus.NEW

    def test_terminal_statuses(self) -> None:
        """CONVERTED, REJECTED, DUPLICATE are terminal."""
        terminal = LeadStatus.terminal_statuses()
        assert LeadStatus.CONVERTED in terminal
        assert LeadStatus.REJECTED in terminal
        assert LeadStatus.DUPLICATE in terminal
        assert LeadStatus.NEW not in terminal


class TestValidTransitions:
    """Tests for allowed status transitions (REQ-041)."""

    @pytest.mark.parametrize("from_status, to_status", [
        ("NEW", "VALIDATED"),
        ("NEW", "REJECTED"),
        ("NEW", "DUPLICATE"),
        ("VALIDATED", "CONTACTED"),
        ("VALIDATED", "REJECTED"),
        ("CONTACTED", "QUALIFIED"),
        ("CONTACTED", "REJECTED"),
        ("QUALIFIED", "CONVERTED"),
        ("QUALIFIED", "REJECTED"),
    ])
    def test_allowed_transitions_do_not_raise(
        self, from_status: str, to_status: str
    ) -> None:
        """REQ-041: All valid transitions pass without exception."""
        validate_transition(LeadStatus(from_status), LeadStatus(to_status))  # No exception


class TestInvalidTransitions:
    """Tests for forbidden status transitions (REQ-041)."""

    @pytest.mark.parametrize("from_status, to_status", [
        ("NEW", "CONTACTED"),
        ("NEW", "QUALIFIED"),
        ("NEW", "CONVERTED"),
        ("VALIDATED", "NEW"),
        ("VALIDATED", "DUPLICATE"),
        ("CONVERTED", "NEW"),
        ("CONVERTED", "VALIDATED"),
        ("CONVERTED", "REJECTED"),
        ("REJECTED", "NEW"),
        ("REJECTED", "VALIDATED"),
        ("DUPLICATE", "NEW"),
        ("DUPLICATE", "VALIDATED"),
    ])
    def test_invalid_transitions_raise_error(
        self, from_status: str, to_status: str
    ) -> None:
        """REQ-041: Forbidden transitions raise InvalidStatusTransitionError."""
        with pytest.raises(InvalidStatusTransitionError) as exc_info:
            validate_transition(LeadStatus(from_status), LeadStatus(to_status))
        assert exc_info.value.error_code == "INVALID_STATUS_TRANSITION"
        assert exc_info.value.from_status == from_status
        assert exc_info.value.to_status == to_status

    def test_terminal_converted_has_no_transitions(self) -> None:
        """CONVERTED is terminal — no outgoing transitions allowed."""
        assert STATUS_TRANSITIONS["CONVERTED"] == frozenset()

    def test_terminal_rejected_has_no_transitions(self) -> None:
        """REJECTED is terminal — no outgoing transitions allowed."""
        assert STATUS_TRANSITIONS["REJECTED"] == frozenset()

    def test_terminal_duplicate_has_no_transitions(self) -> None:
        """DUPLICATE is terminal — no outgoing transitions allowed."""
        assert STATUS_TRANSITIONS["DUPLICATE"] == frozenset()
