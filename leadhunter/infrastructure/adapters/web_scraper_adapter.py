"""Web scraper adapter — Infrastructure layer (REQ-009 through REQ-016).

Implements HTTP fetching with retry, rate-limiting, robots.txt checking,
and HTML parsing via BeautifulSoup4.

Security:
  - User-Agent is hardcoded (LeadHunterBot/1.0), not user-controlled (REQ-015).
  - URL scheme validated before request (http/https only) to prevent SSRF.
  - Private/loopback IP ranges blocked to prevent internal network SSRF.
  - robots.txt compliance enforced (REQ-014).
  - All HTTP requests have explicit timeouts (REQ-011, REQ-071).
  - Retry only on transient errors — not on 4xx responses (REQ-012).
"""

from __future__ import annotations

import logging
import re
import time
import urllib.robotparser
from collections import defaultdict
from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from leadhunter.domain.constants import SCRAPER_USER_AGENT
from leadhunter.domain.exceptions import (
    HttpRequestError,
    RequestTimeoutError,
    RobotsDisallowedError,
)

logger = logging.getLogger(__name__)

# Private/internal IP address ranges — blocked to prevent SSRF attacks
_PRIVATE_IP_PATTERNS = re.compile(
    r"^(127\.|10\.|172\.(1[6-9]|2\d|3[01])\.|192\.168\.|::1|localhost)",
    re.IGNORECASE,
)

# HTTP status codes that are retryable (REQ-012)
_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


class WebScraperAdapter:
    """Scrapes lead data from static HTML pages (REQ-009-016).

    Implements exponential backoff retry, rate limiting per domain,
    robots.txt compliance, and explicit timeouts.

    Args:
        http_timeout: Maximum seconds to wait for a single HTTP request.
        retry_max_attempts: Maximum number of retry attempts per URL.
        rate_limit_delay: Minimum seconds between requests to the same domain.
        extraction_rules: Domain-specific CSS selector rules (optional).
        cache_ttl_hours: How long to cache raw HTML (0 to disable, REQ-016).
    """

    def __init__(
        self,
        http_timeout: float = 10.0,
        retry_max_attempts: int = 3,
        rate_limit_delay: float = 1.0,
        extraction_rules: dict[str, Any] | None = None,
        cache_ttl_hours: float = 24.0,
    ) -> None:
        self._timeout = http_timeout
        self._retry_max = retry_max_attempts
        self._rate_limit_delay = rate_limit_delay
        self._extraction_rules = extraction_rules or {}
        self._cache_ttl_hours = cache_ttl_hours
        self._domain_last_request: dict[str, float] = defaultdict(float)
        self._robots_cache: dict[str, urllib.robotparser.RobotFileParser] = {}
        self._html_cache: dict[str, tuple[str, float]] = {}  # url → (html, timestamp)

        self._session = requests.Session()
        self._session.headers.update({"User-Agent": SCRAPER_USER_AGENT})

    def scrape(self, url: str) -> list[dict[str, str]]:
        """Fetch and extract lead data from a URL.

        Args:
            url: Target URL to scrape.

        Returns:
            List of raw field dictionaries (may be empty if no leads found).

        Raises:
            RobotsDisallowedError: If robots.txt forbids the URL (REQ-014).
            RequestTimeoutError: If the request times out (REQ-011).
            HttpRequestError: On non-retryable HTTP errors.
        """
        self._validate_url_security(url)
        parsed = urlparse(url)
        domain = parsed.netloc

        # REQ-014: Check robots.txt
        if not self._is_allowed_by_robots(url, domain):
            raise RobotsDisallowedError(url)

        # REQ-013: Rate limiting per domain
        self._apply_rate_limit(domain)

        html = self._fetch_with_retry(url)
        return self._extract_leads(html, url)

    def _validate_url_security(self, url: str) -> None:
        """Validate URL scheme and block private/loopback addresses (SSRF prevention).

        Args:
            url: URL to validate.

        Raises:
            HttpRequestError: If the URL is not http/https or targets a private IP.
        """
        parsed = urlparse(url)
        if parsed.scheme.lower() not in ("http", "https"):
            raise HttpRequestError(url, cause=ValueError("Only http/https URLs are allowed"))

        host = parsed.hostname or ""
        if _PRIVATE_IP_PATTERNS.match(host):
            raise HttpRequestError(url, cause=ValueError(f"Blocked host: {host}"))

    def _is_allowed_by_robots(self, url: str, domain: str) -> bool:
        """Check robots.txt for the given URL (REQ-014).

        Args:
            url: Full URL to check.
            domain: Domain to fetch robots.txt from.

        Returns:
            True if crawling is permitted, False if disallowed.
        """
        if domain not in self._robots_cache:
            parsed = urlparse(url)
            robots_url = f"{parsed.scheme}://{domain}/robots.txt"
            rp = urllib.robotparser.RobotFileParser()
            rp.set_url(robots_url)
            try:
                rp.read()
            except Exception:
                # If robots.txt cannot be fetched, assume allowed (common practice)
                rp = urllib.robotparser.RobotFileParser()
            self._robots_cache[domain] = rp

        return self._robots_cache[domain].can_fetch(SCRAPER_USER_AGENT, url)

    def _apply_rate_limit(self, domain: str) -> None:
        """Enforce minimum delay between requests to the same domain (REQ-013).

        Args:
            domain: Domain string (netloc).
        """
        last = self._domain_last_request[domain]
        elapsed = time.monotonic() - last
        if elapsed < self._rate_limit_delay:
            time.sleep(self._rate_limit_delay - elapsed)
        self._domain_last_request[domain] = time.monotonic()

    def _fetch_with_retry(self, url: str) -> str:
        """Fetch the HTML content of a URL with exponential backoff (REQ-012).

        Retries on transient errors (timeouts, 5xx, 429).
        Does NOT retry on 4xx errors (except 429) per REQ-012.

        Args:
            url: Target URL.

        Returns:
            HTML content string.

        Raises:
            RequestTimeoutError: If all attempts timed out.
            HttpRequestError: On non-retryable error.
        """
        # Check HTML cache first (REQ-016)
        if self._cache_ttl_hours > 0 and url in self._html_cache:
            cached_html, cached_at = self._html_cache[url]
            age_hours = (time.monotonic() - cached_at) / 3600
            if age_hours < self._cache_ttl_hours:
                logger.debug("Cache hit", extra={"context": {"url": url}})
                return cached_html

        last_exc: Exception | None = None
        for attempt in range(1, self._retry_max + 1):
            try:
                response = self._session.get(
                    url,
                    timeout=self._timeout,
                    allow_redirects=True,
                )
                if response.status_code == 200:
                    html = response.text
                    if self._cache_ttl_hours > 0:
                        self._html_cache[url] = (html, time.monotonic())
                    return html

                if response.status_code in _RETRYABLE_STATUS_CODES:
                    wait = 2 ** (attempt - 1)  # 1s, 2s, 4s backoff
                    logger.warning(
                        "HTTP error, retrying",
                        extra={
                            "context": {
                                "url": url,
                                "status": response.status_code,
                                "attempt": attempt,
                                "wait_seconds": wait,
                            }
                        },
                    )
                    time.sleep(wait)
                    continue

                # Non-retryable 4xx
                raise HttpRequestError(url, status_code=response.status_code)

            except requests.Timeout as exc:
                last_exc = exc
                wait = 2 ** (attempt - 1)
                logger.warning(
                    "Request timed out, retrying",
                    extra={"context": {"url": url, "attempt": attempt, "wait": wait}},
                )
                if attempt < self._retry_max:
                    time.sleep(wait)

            except requests.ConnectionError as exc:
                last_exc = exc
                wait = 2 ** (attempt - 1)
                logger.warning(
                    "Connection error, retrying",
                    extra={"context": {"url": url, "attempt": attempt}},
                )
                if attempt < self._retry_max:
                    time.sleep(wait)

        if isinstance(last_exc, requests.Timeout):
            raise RequestTimeoutError(url, self._timeout)
        raise HttpRequestError(url, cause=last_exc)

    def _extract_leads(self, html: str, source_url: str) -> list[dict[str, str]]:
        """Extract lead data from HTML content using configured rules.

        Uses BeautifulSoup4 for HTML parsing (REQ-010: static HTML only).
        Falls back to generic email/phone extraction if no domain rules defined.

        Args:
            html: Raw HTML string.
            source_url: URL the HTML was fetched from (for rule matching).

        Returns:
            List of raw field dictionaries.
        """
        soup = BeautifulSoup(html, "html.parser")
        domain = urlparse(source_url).netloc
        rules = self._extraction_rules.get(domain, {})

        if rules:
            return self._extract_with_rules(soup, rules, source_url)
        return self._extract_generic(soup, source_url)

    def _extract_with_rules(
        self,
        soup: BeautifulSoup,
        rules: dict[str, str],
        source_url: str,
    ) -> list[dict[str, str]]:
        """Extract lead data using CSS selector rules.

        Args:
            soup: Parsed HTML document.
            rules: Mapping of field_name → CSS selector string.
            source_url: Original URL for reference.

        Returns:
            List of raw field dictionaries.
        """
        record: dict[str, str] = {}
        for field, selector in rules.items():
            elements = soup.select(selector)
            record[field] = elements[0].get_text(strip=True) if elements else ""
        return [record] if any(record.values()) else []

    def _extract_generic(
        self,
        soup: BeautifulSoup,
        source_url: str,
    ) -> list[dict[str, str]]:
        """Generic email and phone extraction using regex patterns.

        Args:
            soup: Parsed HTML document.
            source_url: Original URL.

        Returns:
            List of raw field dictionaries (one per unique email found).
        """
        text = soup.get_text(separator=" ")

        email_pattern = re.compile(
            r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
        )
        phone_pattern = re.compile(
            r"(?:\+?\d[\d\s\-().]{7,}\d)"
        )

        emails = list(set(email_pattern.findall(text)))
        phones = phone_pattern.findall(text)

        records = []
        for i, email in enumerate(emails):
            record: dict[str, str] = {
                "email": email,
                "phone": phones[i].strip() if i < len(phones) else "",
                "company_name": soup.title.get_text(strip=True) if soup.title else "",
                "contact_name": "",
                "website": source_url,
                "address": "",
            }
            records.append(record)
        return records
