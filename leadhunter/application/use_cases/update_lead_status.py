"""UpdateLeadStatusUseCase — Application layer (REQ-036 through REQ-042)."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from leadhunter.application.dtos import UpdateStatusInputDTO, UpdateStatusResultDTO
from leadhunter.application.ports.lead_repository import LeadRepository
from leadhunter.domain.entities.lead import LeadStatus, LeadStatusHistory
from leadhunter.domain.exceptions import LeadNotFoundError, ValidationError
from leadhunter.domain.services.status_service import validate_transition

logger = logging.getLogger(__name__)


class UpdateLeadStatusUseCase:
    """Update the lifecycle status of a lead (REQ-036 through REQ-042).

    Validates the transition against the STATUS_TRANSITIONS matrix (REQ-041),
    persists the new status, and records a history entry (REQ-037).

    Args:
        repository: LeadRepository implementation.
    """

    def __init__(self, repository: LeadRepository) -> None:
        self._repository = repository

    def execute(self, dto: UpdateStatusInputDTO) -> UpdateStatusResultDTO:
        """Perform the status update.

        Args:
            dto: Input containing lead_id, new_status, actor, reason.

        Returns:
            UpdateStatusResultDTO with old and new status values.

        Raises:
            ValidationError: If new_status is not a known LeadStatus value.
            LeadNotFoundError: If no lead with the given ID exists.
            InvalidStatusTransitionError: If the transition is not allowed.
        """
        start_time = time.monotonic()
        logger.info(
            "UpdateLeadStatusUseCase started",
            extra={
                "context": {
                    "lead_id": dto.lead_id,
                    "new_status": dto.new_status,
                    "actor": dto.actor,
                }
            },
        )

        # Validate target status
        try:
            target_status = LeadStatus(dto.new_status.upper())
        except ValueError:
            raise ValidationError(
                "new_status", f"Unknown status: '{dto.new_status}'"
            )

        lead = self._repository.get_by_id(dto.lead_id)
        if lead is None:
            raise LeadNotFoundError(dto.lead_id)

        old_status = lead.status
        # Domain service validates the transition matrix (REQ-040, REQ-041)
        validate_transition(old_status, target_status)

        lead.status = target_status
        lead.touch()
        self._repository.update(lead)

        history_entry = LeadStatusHistory(
            lead_id=lead.id,
            old_status=old_status,
            new_status=target_status,
            actor=dto.actor,
            reason=dto.reason,
        )
        self._repository.add_status_history(history_entry)

        elapsed_ms = (time.monotonic() - start_time) * 1000
        logger.info(
            "UpdateLeadStatusUseCase completed",
            extra={
                "context": {
                    "lead_id": lead.id,
                    "old_status": old_status.value,
                    "new_status": target_status.value,
                    "elapsed_ms": round(elapsed_ms, 2),
                }
            },
        )

        return UpdateStatusResultDTO(
            lead_id=lead.id,
            old_status=old_status.value,
            new_status=target_status.value,
            changed_at=history_entry.changed_at.isoformat(),
        )
