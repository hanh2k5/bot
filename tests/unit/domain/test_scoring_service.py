"""Unit tests for scoring service (REQ-049-055)."""

import pytest

from leadhunter.domain.entities.lead import Lead, LeadStatus
from leadhunter.domain.services.scoring_service import (
    ScoringRule,
    ScoringRules,
    compute_score,
)


def _make_lead(**kwargs) -> Lead:
    """Create a test Lead with sensible defaults."""
    defaults = {
        "company_name": "Test Corp",
        "contact_name": "Test User",
        "email": "test@example.com",
        "phone": "+84912345678",
        "website": "https://test.com",
        "address": "123 Test St",
        "source": "excel",
        "source_reference": "test.xlsx",
        "phone_normalized": True,
    }
    defaults.update(kwargs)
    return Lead(**defaults)


_FULL_RULES = ScoringRules(
    rules=[
        ScoringRule(field="email", condition="valid", points=20),
        ScoringRule(field="phone", condition="valid", points=15),
        ScoringRule(field="website", condition="valid", points=10),
        ScoringRule(field="completeness", condition="completeness", weight=55),
    ]
)


class TestComputeScore:
    """Tests for compute_score pure function (REQ-052)."""

    def test_fully_filled_lead_scores_100(self) -> None:
        """REQ-052: Fully filled, normalised lead scores 100."""
        lead = _make_lead()
        score = compute_score(lead, _FULL_RULES)
        assert score == 100

    def test_empty_lead_scores_low(self) -> None:
        """Lead with no email, phone, or website scores low."""
        lead = _make_lead(email="", phone="", website="", phone_normalized=False)
        score = compute_score(lead, _FULL_RULES)
        assert score < 50

    def test_score_clamps_at_100(self) -> None:
        """REQ-051: Score never exceeds 100."""
        # Rules that could sum to more than 100
        big_rules = ScoringRules(rules=[
            ScoringRule(field="email", condition="valid", points=80),
            ScoringRule(field="phone", condition="valid", points=80),
        ])
        lead = _make_lead()
        score = compute_score(lead, big_rules)
        assert score <= 100

    def test_score_clamps_at_0(self) -> None:
        """REQ-051: Score is never negative."""
        lead = _make_lead(email="", phone="", website="")
        score = compute_score(lead, _FULL_RULES)
        assert score >= 0

    def test_pure_function_same_input_same_output(self) -> None:
        """REQ-052: Pure function — same input always yields same output."""
        lead = _make_lead()
        score1 = compute_score(lead, _FULL_RULES)
        score2 = compute_score(lead, _FULL_RULES)
        assert score1 == score2

    def test_empty_rules_scores_zero(self) -> None:
        """No rules → score 0."""
        lead = _make_lead()
        score = compute_score(lead, ScoringRules(rules=[]))
        assert score == 0

    def test_email_rule_only_no_email_scores_zero(self) -> None:
        """Email rule with no email → 0 points."""
        rules = ScoringRules(rules=[ScoringRule(field="email", condition="valid", points=20)])
        lead = _make_lead(email="")
        score = compute_score(lead, rules)
        assert score == 0

    def test_phone_valid_rule_requires_normalized(self) -> None:
        """Phone 'valid' rule only fires if phone_normalized is True."""
        rules = ScoringRules(rules=[ScoringRule(field="phone", condition="valid", points=15)])
        lead_normalized = _make_lead(phone="+84912345678", phone_normalized=True)
        lead_not_normalized = _make_lead(phone="123456", phone_normalized=False)
        assert compute_score(lead_normalized, rules) == 15
        assert compute_score(lead_not_normalized, rules) == 0

    def test_completeness_partial_fill(self) -> None:
        """Partial completeness scales linearly."""
        rules = ScoringRules(rules=[
            ScoringRule(field="completeness", condition="completeness", weight=60)
        ])
        # 3 of 6 completeness fields filled
        lead = _make_lead(
            company_name="Corp",
            contact_name="",
            email="a@b.com",
            phone="",
            website="",
            address="Addr",
        )
        score = compute_score(lead, rules)
        # 3/6 = 0.5, 0.5 * 60 = 30
        assert score == 30
