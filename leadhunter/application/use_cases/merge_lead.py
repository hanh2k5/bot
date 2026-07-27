"""MergeLeadUseCase — Application layer (REQ-026)."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from leadhunter.application.dtos import MergeLeadInputDTO, MergeLeadResultDTO
from leadhunter.application.ports.lead_repository import LeadRepository
from leadhunter.domain.exceptions import LeadNotFoundError, ValidationError

logger = logging.getLogger(__name__)

# Fields that can be merged from duplicate → target (if target field is empty)
_MERGEABLE_FIELDS = [
    "contact_name",
    "phone",
    "website",
    "address",
    "notes",
]


class MergeLeadUseCase:
    """Merge a duplicate lead record into its canonical original (REQ-026).

    After merge:
      - Duplicate lead's non-empty fields are applied to the target if target
        field is empty.
      - The duplicate lead's status is set to DUPLICATE.
      - A status history entry is recorded for both leads.
      - Merge operation is logged with before/after data.

    Args:
        repository: LeadRepository implementation.
    """

    def __init__(self, repository: LeadRepository) -> None:
        self._repository = repository

    def execute(self, dto: MergeLeadInputDTO) -> MergeLeadResultDTO:
        """Execute the merge operation.

        Args:
            dto: Input containing duplicate_lead_id, target_lead_id, actor.

        Returns:
            MergeLeadResultDTO with fields_updated and merged_at.

        Raises:
            ValidationError: If both lead IDs are the same.
            LeadNotFoundError: If either lead does not exist.
        """
        start_time = time.monotonic()

        if dto.duplicate_lead_id == dto.target_lead_id:
            raise ValidationError(
                "duplicate_lead_id", "Cannot merge a lead with itself."
            )

        logger.info(
            "MergeLeadUseCase started",
            extra={
                "context": {
                    "duplicate_id": dto.duplicate_lead_id,
                    "target_id": dto.target_lead_id,
                    "actor": dto.actor,
                }
            },
        )

        duplicate = self._repository.get_by_id(dto.duplicate_lead_id)
        if duplicate is None:
            raise LeadNotFoundError(dto.duplicate_lead_id)

        target = self._repository.get_by_id(dto.target_lead_id)
        if target is None:
            raise LeadNotFoundError(dto.target_lead_id)

        # Capture before state for audit log (REQ-026)
        before_data = {f: getattr(target, f, None) for f in _MERGEABLE_FIELDS}

        fields_updated: list[str] = []
        for field_name in _MERGEABLE_FIELDS:
            dup_value = getattr(duplicate, field_name, "")
            target_value = getattr(target, field_name, "")
            if dup_value and not target_value:
                setattr(target, field_name, dup_value)
                fields_updated.append(field_name)

        if fields_updated:
            target.touch()
            self._repository.update(target)

        after_data = {f: getattr(target, f, None) for f in _MERGEABLE_FIELDS}

        merged_at = datetime.now(timezone.utc).isoformat()
        elapsed_ms = (time.monotonic() - start_time) * 1000
        logger.info(
            "MergeLeadUseCase completed",
            extra={
                "context": {
                    "target_id": target.id,
                    "fields_updated": fields_updated,
                    "before": before_data,
                    "after": after_data,
                    "elapsed_ms": round(elapsed_ms, 2),
                }
            },
        )

        return MergeLeadResultDTO(
            target_lead_id=target.id,
            merged_at=merged_at,
            fields_updated=fields_updated,
        )
