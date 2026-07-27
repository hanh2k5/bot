"""ScrapeLeadsFromUrlsUseCase — Application layer (REQ-009 through REQ-016)."""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from leadhunter.application.dtos import (
    ScrapeResultDTO,
    ScrapeUrlErrorDTO,
)
from leadhunter.application.ports.lead_repository import LeadRepository
from leadhunter.domain.entities.lead import DuplicateLog, ImportHistory, Lead, LeadStatus
from leadhunter.domain.exceptions import (
    DomainError,
    InfrastructureError,
    RobotsDisallowedError,
    RequestTimeoutError,
)
from leadhunter.domain.services.dedup_service import (
    DeduplicationConfig,
    compute_email_dedup_key,
)
from leadhunter.domain.services.normalization_service import (
    normalize_address,
    normalize_company_name,
    normalize_contact_name,
    normalize_email,
    normalize_phone,
    normalize_website,
)

logger = logging.getLogger(__name__)


class ScrapeLeadsFromUrlsUseCase:
    """Scrape leads from a list of URLs (REQ-009 through REQ-016).

    Delegates HTTP fetching and HTML parsing to the web scraper adapter.
    Each URL is processed independently (idempotent, NFR-005).

    Args:
        repository: LeadRepository implementation.
        scraper_adapter: WebScraperAdapter implementation.
        dedup_config: Deduplication configuration.
        max_urls: Maximum URLs per run (REQ-009).
        actor: User/process identifier.
    """

    def __init__(
        self,
        repository: LeadRepository,
        scraper_adapter: "WebScraperAdapter",  # type: ignore[name-defined]
        dedup_config: Optional[DeduplicationConfig] = None,
        max_urls: int = 500,
        actor: str = "cli",
    ) -> None:
        self._repository = repository
        self._scraper_adapter = scraper_adapter
        self._dedup_config = dedup_config or DeduplicationConfig()
        self._max_urls = max_urls
        self._actor = actor

    def execute(self, urls: list[str]) -> ScrapeResultDTO:
        """Scrape leads from the provided URL list.

        Args:
            urls: List of URLs to scrape (max self._max_urls, REQ-009).

        Returns:
            ScrapeResultDTO with counts and per-URL errors.
        """
        batch_id = str(uuid.uuid4())
        start_time = time.monotonic()
        urls_to_process = urls[: self._max_urls]

        logger.info(
            "ScrapeLeadsFromUrlsUseCase started",
            extra={
                "context": {
                    "import_batch_id": batch_id,
                    "url_count": len(urls_to_process),
                    "actor": self._actor,
                }
            },
        )

        success_count = 0
        error_count = 0
        duplicate_count = 0
        url_errors: list[ScrapeUrlErrorDTO] = []

        for url in urls_to_process:
            try:
                raw_records = self._scraper_adapter.scrape(url)
                for raw in raw_records:
                    try:
                        lead = self._build_lead(raw, batch_id, url)
                    except DomainError as exc:
                        error_count += 1
                        url_errors.append(
                            ScrapeUrlErrorDTO(
                                url=url,
                                error_code=exc.error_code,
                                message=exc.message,
                            )
                        )
                        continue

                    dup_id = self._find_duplicate(lead)
                    if dup_id is not None:
                        duplicate_count += 1
                        dup_log = DuplicateLog(
                            original_lead_id=dup_id,
                            duplicate_data=json.dumps(raw),
                            import_batch_id=batch_id,
                        )
                        self._repository.add_duplicate_log(dup_log)
                        continue

                    self._repository.add(lead)
                    success_count += 1

            except RobotsDisallowedError as exc:
                error_count += 1
                url_errors.append(
                    ScrapeUrlErrorDTO(
                        url=url,
                        error_code=exc.error_code,
                        message=exc.message,
                    )
                )
            except RequestTimeoutError as exc:
                error_count += 1
                url_errors.append(
                    ScrapeUrlErrorDTO(
                        url=url,
                        error_code=exc.error_code,
                        message=exc.message,
                    )
                )
            except InfrastructureError as exc:
                error_count += 1
                url_errors.append(
                    ScrapeUrlErrorDTO(
                        url=url,
                        error_code=exc.error_code,
                        message=exc.message,
                    )
                )

        history = ImportHistory(
            import_batch_id=batch_id,
            source_file_name=f"web_scrape_{len(urls_to_process)}_urls",
            actor=self._actor,
            success_count=success_count,
            error_count=error_count,
            duplicate_count=duplicate_count,
        )
        self._repository.add_import_history(history)

        elapsed_ms = (time.monotonic() - start_time) * 1000
        logger.info(
            "ScrapeLeadsFromUrlsUseCase completed",
            extra={
                "context": {
                    "import_batch_id": batch_id,
                    "success_count": success_count,
                    "error_count": error_count,
                    "duplicate_count": duplicate_count,
                    "elapsed_ms": round(elapsed_ms, 2),
                }
            },
        )

        return ScrapeResultDTO(
            import_batch_id=batch_id,
            success_count=success_count,
            error_count=error_count,
            duplicate_count=duplicate_count,
            url_errors=url_errors,
            executed_at=datetime.now(timezone.utc).isoformat(),
        )

    def _build_lead(
        self, raw: dict[str, str], batch_id: str, source_url: str
    ) -> Lead:
        """Build a normalised Lead from scraped raw data.

        Args:
            raw: Raw field → value mapping from scraper.
            batch_id: Import batch UUID.
            source_url: The URL this data was scraped from.

        Returns:
            Normalised Lead entity.

        Raises:
            DomainError: On validation failure.
        """
        email_vo = normalize_email(raw.get("email", ""))
        phone_vo = normalize_phone(raw.get("phone", ""))
        company_vo = normalize_company_name(raw.get("company_name", ""))

        website_raw = raw.get("website", "").strip()
        try:
            website_str = normalize_website(website_raw).value if website_raw else ""
        except DomainError:
            website_str = website_raw

        return Lead(
            company_name=company_vo.value,
            contact_name=normalize_contact_name(raw.get("contact_name", "")),
            email=email_vo.value,
            phone=phone_vo.value,
            website=website_str,
            address=normalize_address(raw.get("address", "")),
            source="web",
            source_reference=source_url,
            status=LeadStatus.NEW,
            import_batch_id=batch_id,
            phone_normalized=phone_vo.normalized,
        )

    def _find_duplicate(self, lead: Lead) -> Optional[str]:
        """Check if a lead is a duplicate.

        Args:
            lead: The Lead to check.

        Returns:
            Existing lead ID if duplicate, None otherwise.
        """
        if self._dedup_config.use_email_dedup and lead.email:
            existing = self._repository.find_by_email(
                compute_email_dedup_key(lead.email)
            )
            if existing is not None:
                return existing.id
        return None


class WebScraperAdapter:
    """Protocol stub for the web scraper adapter (lives in Infrastructure)."""

    def scrape(self, url: str) -> list[dict[str, str]]:
        """Scrape leads from a URL.

        Args:
            url: The target URL.

        Returns:
            List of raw field dictionaries.
        """
        raise NotImplementedError
