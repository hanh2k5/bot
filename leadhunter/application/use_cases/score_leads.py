"""ScoreLeadUseCase and ScoreLeadsBatchUseCase — Application layer (REQ-049-055)."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Optional

from leadhunter.application.dtos import BatchScoreResultDTO, ScoreResultDTO
from leadhunter.application.ports.lead_repository import LeadRepository
from leadhunter.domain.exceptions import LeadNotFoundError
from leadhunter.domain.services.scoring_service import ScoringRules, compute_score

logger = logging.getLogger(__name__)


class ScoreLeadUseCase:
    """Score a single lead based on configurable scoring rules (REQ-049-055).

    Args:
        repository: LeadRepository implementation.
        scoring_rules: The active scoring ruleset.
    """

    def __init__(
        self, repository: LeadRepository, scoring_rules: ScoringRules
    ) -> None:
        self._repository = repository
        self._scoring_rules = scoring_rules

    def execute(self, lead_id: str) -> ScoreResultDTO:
        """Compute and persist the score for one lead.

        Args:
            lead_id: UUID of the lead to score.

        Returns:
            ScoreResultDTO with old_score and new_score.

        Raises:
            LeadNotFoundError: If the lead does not exist.
        """
        logger.info(
            "ScoreLeadUseCase started",
            extra={"context": {"lead_id": lead_id}},
        )

        lead = self._repository.get_by_id(lead_id)
        if lead is None:
            raise LeadNotFoundError(lead_id)

        old_score = lead.score
        new_score = compute_score(lead, self._scoring_rules)

        if new_score != old_score:
            lead.score = new_score
            lead.touch()
            self._repository.update(lead)
            logger.info(
                "Lead score updated",
                extra={
                    "context": {
                        "lead_id": lead_id,
                        "old_score": old_score,
                        "new_score": new_score,
                    }
                },
            )

        return ScoreResultDTO(
            lead_id=lead_id,
            old_score=old_score,
            new_score=new_score,
            updated_at=lead.updated_at.isoformat(),
        )


class ScoreLeadsBatchUseCase:
    """Score all leads in configurable batches (REQ-053, REQ-054).

    Processes leads in batches to avoid loading the entire table into memory.

    Args:
        repository: LeadRepository implementation.
        scoring_rules: The active scoring ruleset.
        batch_size: Number of leads to process per batch (REQ-054).
    """

    def __init__(
        self,
        repository: LeadRepository,
        scoring_rules: ScoringRules,
        batch_size: int = 500,
    ) -> None:
        self._repository = repository
        self._scoring_rules = scoring_rules
        self._batch_size = batch_size

    def execute(self) -> BatchScoreResultDTO:
        """Score all leads in the repository in batches.

        Returns:
            BatchScoreResultDTO with processed_count, updated_count, elapsed_ms.
        """
        start_time = time.monotonic()
        logger.info(
            "ScoreLeadsBatchUseCase started",
            extra={"context": {"batch_size": self._batch_size}},
        )

        processed_count = 0
        updated_count = 0
        page = 1

        while True:
            batch = self._repository.list(
                page=page,
                page_size=self._batch_size,
                sort_by="created_at",
                sort_order="asc",
                include_duplicates=False,
            )
            if not batch:
                break

            for lead in batch:
                old_score = lead.score
                new_score = compute_score(lead, self._scoring_rules)
                if new_score != old_score:
                    lead.score = new_score
                    lead.touch()
                    self._repository.update(lead)
                    updated_count += 1
                processed_count += 1

            page += 1

        elapsed_ms = (time.monotonic() - start_time) * 1000
        logger.info(
            "ScoreLeadsBatchUseCase completed",
            extra={
                "context": {
                    "processed_count": processed_count,
                    "updated_count": updated_count,
                    "elapsed_ms": round(elapsed_ms, 2),
                }
            },
        )

        return BatchScoreResultDTO(
            processed_count=processed_count,
            updated_count=updated_count,
            elapsed_ms=elapsed_ms,
        )
