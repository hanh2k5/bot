"""Domain scoring service.

Pure function for computing a lead's score based on a configurable ruleset
(REQ-049, REQ-052). No I/O, no database, no hidden state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from leadhunter.domain.constants import SCORE_MAX, SCORE_MIN
from leadhunter.domain.entities.lead import Lead


@dataclass(frozen=True)
class ScoringRule:
    """A single configurable scoring rule.

    Attributes:
        field: Lead field to evaluate (e.g. 'email', 'phone', 'website').
        condition: Condition type ('valid', 'not_empty', 'completeness').
        points: Points awarded when the condition is met (for fixed rules).
        weight: For 'completeness' rules: total points available, scaled
            by (filled_fields / total_fields). Ignored for other conditions.
    """

    field: str
    condition: str
    points: int = 0
    weight: int = 0


@dataclass(frozen=True)
class ScoringRules:
    """Complete set of scoring rules loaded from configuration (REQ-055).

    Attributes:
        rules: List of individual scoring rules.
    """

    rules: list[ScoringRule] = field(default_factory=list)


def compute_score(lead: Lead, rules: ScoringRules) -> int:
    """Compute the score for a lead based on the provided ruleset.

    This is a pure function: same inputs always produce the same output.
    No I/O, no timestamps, no hidden state (REQ-052).

    Args:
        lead: The Lead entity to score.
        rules: The active ScoringRules configuration.

    Returns:
        Integer score clamped to [SCORE_MIN, SCORE_MAX] (REQ-051).
    """
    total: float = 0.0

    # Fields considered for completeness calculation
    completeness_fields = [
        "company_name",
        "contact_name",
        "email",
        "phone",
        "website",
        "address",
    ]

    for rule in rules.rules:
        if rule.condition == "valid" and rule.field == "email":
            if lead.email:
                total += rule.points

        elif rule.condition == "valid" and rule.field == "phone":
            if lead.phone and lead.phone_normalized:
                total += rule.points

        elif rule.condition == "valid" and rule.field == "website":
            if lead.website:
                total += rule.points

        elif rule.condition == "not_empty":
            value = _get_field(lead, rule.field)
            if value:
                total += rule.points

        elif rule.condition == "completeness":
            filled = sum(
                1 for f in completeness_fields if _get_field(lead, f)
            )
            ratio = filled / len(completeness_fields) if completeness_fields else 0.0
            total += rule.weight * ratio

    # Clamp to valid range (REQ-051)
    clamped = max(SCORE_MIN, min(SCORE_MAX, int(round(total))))
    return clamped


def _get_field(lead: Lead, field_name: str) -> Any:
    """Safely get a field value from a Lead, returning None if missing.

    Args:
        lead: The Lead entity.
        field_name: Attribute name to retrieve.

    Returns:
        The field value, or None if the attribute does not exist.
    """
    return getattr(lead, field_name, None)
