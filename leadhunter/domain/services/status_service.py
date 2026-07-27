"""Status transition domain service.

Validates lead status transitions against the authoritative matrix (REQ-041).
"""

from __future__ import annotations

from leadhunter.domain.constants import STATUS_TRANSITIONS
from leadhunter.domain.entities.lead import LeadStatus
from leadhunter.domain.exceptions import InvalidStatusTransitionError


def validate_transition(current: LeadStatus, target: LeadStatus) -> None:
    """Assert that transitioning from ``current`` to ``target`` is permitted.

    Args:
        current: The lead's current status.
        target: The desired next status.

    Raises:
        InvalidStatusTransitionError: If the transition is not in the
            STATUS_TRANSITIONS matrix.
    """
    allowed = STATUS_TRANSITIONS.get(current.value, frozenset())
    if target.value not in allowed:
        raise InvalidStatusTransitionError(current.value, target.value)
