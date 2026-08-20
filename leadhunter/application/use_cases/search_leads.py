"""SearchLeadsUseCase — Application layer (REQ-043 through REQ-048)."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Optional

from leadhunter.application.dtos import LeadDTO, SearchParamsDTO, SearchResultDTO
from leadhunter.application.ports.lead_repository import LeadRepository
from leadhunter.domain.entities.lead import LeadStatus
from leadhunter.domain.exceptions import ValidationError

logger = logging.getLogger(__name__)

_SORTABLE_FIELDS = frozenset({"created_at", "score", "company_name", "updated_at"})
_SORT_ORDERS = frozenset({"asc", "desc"})
_MAX_PAGE_SIZE_DEFAULT = 200


class SearchLeadsUseCase:
    """Search and filter leads with pagination and sorting (REQ-043-048).

    Args:
        repository: LeadRepository implementation.
        max_page_size: Maximum allowed page_size (configurable, REQ-044).
        default_page_size: Default page_size if not specified.
    """

    def __init__(
        self,
        repository: LeadRepository,
        max_page_size: int = _MAX_PAGE_SIZE_DEFAULT,
        default_page_size: int = 20,
    ) -> None:
        self._repository = repository
        self._max_page_size = max_page_size
        self._default_page_size = default_page_size

    def execute(self, params: SearchParamsDTO) -> SearchResultDTO:
        """Run the search query.

        Args:
            params: Search parameters DTO.

        Returns:
            Paginated SearchResultDTO with leads and total_count.

        Raises:
            ValidationError: If any parameter is invalid (REQ-046).
        """
        start_time = time.monotonic()
        validated = self._validate(params)

        logger.info(
            "SearchLeadsUseCase started",
            extra={"context": {"params": vars(validated)}},
        )

        status_enum: Optional[LeadStatus] = None
        if validated.status:
            try:
                status_enum = LeadStatus(validated.status.upper())
            except ValueError:
                raise ValidationError("status", f"Unknown status: '{validated.status}'")

        leads = self._repository.list(
            status=status_enum,
            score_min=validated.score_min,
            score_max=validated.score_max,
            source=validated.source,
            keyword=validated.keyword,
            created_from=validated.created_from,
            created_to=validated.created_to,
            include_duplicates=validated.include_duplicates,
            page=validated.page,
            page_size=validated.page_size,
            sort_by=validated.sort_by,
            sort_order=validated.sort_order,
        )
        total_count = self._repository.count(
            status=status_enum,
            score_min=validated.score_min,
            score_max=validated.score_max,
            source=validated.source,
            keyword=validated.keyword,
            created_from=validated.created_from,
            created_to=validated.created_to,
            include_duplicates=validated.include_duplicates,
        )

        lead_dtos = [_lead_to_dto(lead) for lead in leads]
        elapsed_ms = (time.monotonic() - start_time) * 1000
        logger.info(
            "SearchLeadsUseCase completed",
            extra={
                "context": {
                    "result_count": len(lead_dtos),
                    "total_count": total_count,
                    "elapsed_ms": round(elapsed_ms, 2),
                }
            },
        )

        return SearchResultDTO(
            leads=lead_dtos,
            total_count=total_count,
            page=validated.page,
            page_size=validated.page_size,
        )

    def _validate(self, params: SearchParamsDTO) -> SearchParamsDTO:
        """Validate and normalise search parameters.

        Args:
            params: Raw parameters from CLI.

        Returns:
            Validated (possibly adjusted) SearchParamsDTO.

        Raises:
            ValidationError: On invalid parameter values.
        """
        if params.page < 1:
            raise ValidationError("page", "Page number must be >= 1")

        page_size = params.page_size or self._default_page_size
        if page_size < 1:
            raise ValidationError("page_size", "Page size must be >= 1")
        if page_size > self._max_page_size:
            page_size = self._max_page_size

        if params.sort_by not in _SORTABLE_FIELDS:
            raise ValidationError(
                "sort_by",
                f"Must be one of: {', '.join(sorted(_SORTABLE_FIELDS))}",
            )
        if params.sort_order.lower() not in _SORT_ORDERS:
            raise ValidationError("sort_order", "Must be 'asc' or 'desc'")

        if params.score_min is not None and params.score_max is not None:
            if params.score_min > params.score_max:
                raise ValidationError(
                    "score_min", "score_min cannot exceed score_max"
                )

        return SearchParamsDTO(
            status=params.status,
            score_min=params.score_min,
            score_max=params.score_max,
            source=params.source,
            keyword=params.keyword,
            created_from=params.created_from,
            created_to=params.created_to,
            include_duplicates=params.include_duplicates,
            page=params.page,
            page_size=page_size,
            sort_by=params.sort_by,
            sort_order=params.sort_order.lower(),
        )


def _lead_to_dto(lead: "Lead") -> LeadDTO:  # type: ignore[name-defined]
    """Convert a Lead entity to a LeadDTO.

    Args:
        lead: The Lead entity to convert.

    Returns:
        LeadDTO snapshot.
    """
    from leadhunter.domain.entities.lead import Lead

    return LeadDTO(
        id=lead.id,
        company_name=lead.company_name,
        contact_name=lead.contact_name,
        email=lead.email,
        phone=lead.phone,
        website=lead.website,
        address=lead.address,
        source=lead.source,
        source_reference=lead.source_reference,
        status=lead.status.value,
        score=lead.score,
        notes=lead.notes,
        created_at=lead.created_at.isoformat(),
        updated_at=lead.updated_at.isoformat(),
        import_batch_id=lead.import_batch_id,
        phone_normalized=lead.phone_normalized,
    )
