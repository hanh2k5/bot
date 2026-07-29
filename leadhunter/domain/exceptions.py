"""Domain layer exceptions hierarchy.

Root: LeadHunterError
  └── DomainError
        ├── InvalidEmailFormatError
        ├── InvalidPhoneFormatError
        ├── InvalidWebsiteError
        ├── InvalidCompanyNameError
        ├── InvalidStatusTransitionError
        └── DuplicateLeadError
  └── ApplicationError
        ├── MissingRequiredColumnError
        ├── FileTooLargeError
        ├── UnsupportedEncodingError
        ├── NoDataToExportError
        └── LeadNotFoundError
  └── InfrastructureError
        ├── DatabaseError
        ├── FileReadError
        ├── FileWriteError
        ├── HttpRequestError
        ├── RobotsDisallowedError
        └── MigrationError
"""

from __future__ import annotations


class LeadHunterError(Exception):
    """Base exception for all LeadHunter errors.

    Attributes:
        error_code: Stable string code used for programmatic handling.
        message: Human-readable error description.
    """

    error_code: str = "LEADHUNTER_ERROR"

    def __init__(self, message: str, error_code: str | None = None) -> None:
        """Initialize the error.

        Args:
            message: Human-readable description of the error.
            error_code: Optional override for the class-level error_code.
        """
        super().__init__(message)
        if error_code is not None:
            self.error_code = error_code
        self.message = message

    def __str__(self) -> str:
        return f"[{self.error_code}] {self.message}"


# ---------------------------------------------------------------------------
# Domain Errors
# ---------------------------------------------------------------------------


class DomainError(LeadHunterError):
    """Base class for all domain-layer errors."""

    error_code = "DOMAIN_ERROR"


class InvalidEmailFormatError(DomainError):
    """Raised when an email address does not conform to RFC 5322 simplified format.

    Args:
        email: The invalid email string that triggered this error.
    """

    error_code = "INVALID_EMAIL_FORMAT"

    def __init__(self, email: str) -> None:
        super().__init__(
            f"Invalid email format: '{email}'. "
            "Expected format: local-part@domain (e.g. user@example.com)"
        )
        self.email = email


class InvalidPhoneFormatError(DomainError):
    """Raised when a phone number cannot be parsed or normalised.

    Args:
        phone: The invalid phone string.
    """

    error_code = "INVALID_PHONE_FORMAT"

    def __init__(self, phone: str) -> None:
        super().__init__(f"Invalid phone number: '{phone}'")
        self.phone = phone


class InvalidWebsiteError(DomainError):
    """Raised when a website URL is structurally invalid.

    Args:
        website: The invalid URL string.
    """

    error_code = "INVALID_WEBSITE"

    def __init__(self, website: str) -> None:
        super().__init__(f"Invalid website URL: '{website}'")
        self.website = website


class InvalidCompanyNameError(DomainError):
    """Raised when a company name is empty after normalisation.

    Args:
        name: The original company name string.
    """

    error_code = "INVALID_COMPANY_NAME"

    def __init__(self, name: str) -> None:
        super().__init__(f"Company name is empty or invalid: '{name}'")
        self.name = name


class InvalidStatusTransitionError(DomainError):
    """Raised when a lead status transition is not permitted by the matrix.

    Args:
        from_status: Current status of the lead.
        to_status: Target status that was requested.
    """

    error_code = "INVALID_STATUS_TRANSITION"

    def __init__(self, from_status: str, to_status: str) -> None:
        super().__init__(
            f"Transition from '{from_status}' to '{to_status}' is not allowed."
        )
        self.from_status = from_status
        self.to_status = to_status


class DuplicateLeadError(DomainError):
    """Raised when a lead already exists in the system based on dedup keys.

    Args:
        existing_lead_id: The ID of the existing lead record.
    """

    error_code = "DUPLICATE_LEAD"

    def __init__(self, existing_lead_id: str) -> None:
        super().__init__(
            f"Lead already exists (existing id: {existing_lead_id})"
        )
        self.existing_lead_id = existing_lead_id


# ---------------------------------------------------------------------------
# Application Errors
# ---------------------------------------------------------------------------


class ApplicationError(LeadHunterError):
    """Base class for all application-layer errors."""

    error_code = "APPLICATION_ERROR"


class MissingRequiredColumnError(ApplicationError):
    """Raised when an import file is missing one or more required columns.

    Args:
        missing_columns: List of column names that are absent.
    """

    error_code = "MISSING_REQUIRED_COLUMN"

    def __init__(self, missing_columns: list[str]) -> None:
        cols = ", ".join(missing_columns)
        super().__init__(
            f"Import file is missing required columns: {cols}. "
            "Import aborted — no records were processed."
        )
        self.missing_columns = missing_columns


class FileTooLargeError(ApplicationError):
    """Raised when an import file exceeds the configured size limit.

    Args:
        file_path: Path to the oversized file.
        max_mb: Configured maximum file size in megabytes.
        actual_mb: Actual file size in megabytes.
    """

    error_code = "FILE_TOO_LARGE"

    def __init__(self, file_path: str, max_mb: float, actual_mb: float) -> None:
        super().__init__(
            f"File '{file_path}' is {actual_mb:.1f} MB, "
            f"which exceeds the maximum allowed size of {max_mb:.1f} MB."
        )
        self.file_path = file_path
        self.max_mb = max_mb
        self.actual_mb = actual_mb


class UnsupportedEncodingError(ApplicationError):
    """Raised when a CSV file uses an unsupported character encoding.

    Args:
        file_path: Path to the file.
        detected_encoding: Encoding that was detected (if any).
    """

    error_code = "UNSUPPORTED_ENCODING"

    def __init__(self, file_path: str, detected_encoding: str | None = None) -> None:
        enc_info = f" (detected: {detected_encoding})" if detected_encoding else ""
        super().__init__(
            f"File '{file_path}' uses an unsupported encoding{enc_info}. "
            "Only UTF-8 and UTF-8-BOM are supported."
        )
        self.file_path = file_path
        self.detected_encoding = detected_encoding


class NoDataToExportError(ApplicationError):
    """Raised when an export query matches zero records.

    Args:
        filter_description: Human-readable description of applied filters.
    """

    error_code = "NO_DATA_TO_EXPORT"

    def __init__(self, filter_description: str = "applied filters") -> None:
        super().__init__(
            f"No records matched the {filter_description}. No file was created."
        )


class LeadNotFoundError(ApplicationError):
    """Raised when a lead with the given ID does not exist.

    Args:
        lead_id: The ID that was not found.
    """

    error_code = "LEAD_NOT_FOUND"

    def __init__(self, lead_id: str) -> None:
        super().__init__(f"Lead with id '{lead_id}' was not found.")
        self.lead_id = lead_id


class ValidationError(ApplicationError):
    """Raised when input parameters fail validation at the use-case layer.

    Args:
        field: The name of the invalid field or parameter.
        reason: Human-readable explanation of the validation failure.
    """

    error_code = "VALIDATION_ERROR"

    def __init__(self, field: str, reason: str) -> None:
        super().__init__(f"Validation failed for '{field}': {reason}")
        self.field = field
        self.reason = reason


# ---------------------------------------------------------------------------
# Infrastructure Errors
# ---------------------------------------------------------------------------


class InfrastructureError(LeadHunterError):
    """Base class for all infrastructure-layer errors.

    Note:
        All third-party library exceptions (sqlite3, requests, openpyxl) must
        be caught in the Infrastructure layer and re-raised as a subclass of
        InfrastructureError before propagating upward (EXC-004).
    """

    error_code = "INFRASTRUCTURE_ERROR"


class DatabaseError(InfrastructureError):
    """Wraps SQLite or other persistence-layer exceptions.

    Args:
        operation: SQL operation that failed (e.g. 'INSERT leads').
        cause: Original exception from sqlite3.
    """

    error_code = "DATABASE_ERROR"

    def __init__(self, operation: str, cause: Exception) -> None:
        super().__init__(
            f"Database operation failed during '{operation}': {type(cause).__name__}"
        )
        self.operation = operation
        self.__cause__ = cause


class FileReadError(InfrastructureError):
    """Raised when a file cannot be read from the filesystem.

    Args:
        file_path: Path to the file that could not be read.
        cause: Original I/O exception.
    """

    error_code = "FILE_READ_ERROR"

    def __init__(self, file_path: str, cause: Exception) -> None:
        super().__init__(
            f"Cannot read file '{file_path}': {type(cause).__name__}"
        )
        self.file_path = file_path
        self.__cause__ = cause


class FileWriteError(InfrastructureError):
    """Raised when a file cannot be written to the filesystem.

    Args:
        file_path: Path to the file that could not be written.
        cause: Original I/O exception.
    """

    error_code = "FILE_WRITE_ERROR"

    def __init__(self, file_path: str, cause: Exception) -> None:
        super().__init__(
            f"Cannot write file '{file_path}': {type(cause).__name__}"
        )
        self.file_path = file_path
        self.__cause__ = cause


class HttpRequestError(InfrastructureError):
    """Wraps network/HTTP errors that occur during web scraping.

    Args:
        url: The URL that triggered the error.
        status_code: HTTP status code, if received.
        cause: Original exception from requests.
    """

    error_code = "HTTP_REQUEST_ERROR"

    def __init__(
        self,
        url: str,
        status_code: int | None = None,
        cause: Exception | None = None,
    ) -> None:
        code_info = f" (HTTP {status_code})" if status_code else ""
        super().__init__(f"HTTP request failed for '{url}'{code_info}")
        self.url = url
        self.status_code = status_code
        if cause is not None:
            self.__cause__ = cause


class RobotsDisallowedError(InfrastructureError):
    """Raised when robots.txt disallows crawling the target URL.

    Args:
        url: The URL that is disallowed.
    """

    error_code = "DISALLOWED_BY_ROBOTS_TXT"

    def __init__(self, url: str) -> None:
        super().__init__(
            f"Crawling '{url}' is disallowed by robots.txt. Request was not sent."
        )
        self.url = url


class RequestTimeoutError(InfrastructureError):
    """Raised when an HTTP request times out.

    Args:
        url: The URL that timed out.
        timeout_seconds: Configured timeout in seconds.
    """

    error_code = "REQUEST_TIMEOUT"

    def __init__(self, url: str, timeout_seconds: float) -> None:
        super().__init__(
            f"Request to '{url}' timed out after {timeout_seconds}s."
        )
        self.url = url
        self.timeout_seconds = timeout_seconds


class MigrationError(InfrastructureError):
    """Raised when a database schema migration fails.

    Args:
        migration_name: Name/number of the migration that failed.
        cause: Original exception.
    """

    error_code = "MIGRATION_ERROR"

    def __init__(self, migration_name: str, cause: Exception) -> None:
        super().__init__(
            f"Schema migration '{migration_name}' failed: {type(cause).__name__}"
        )
        self.migration_name = migration_name
        self.__cause__ = cause

class GoogleMapsBlockedError(InfrastructureError):
    """Raised when Google Maps blocks the scraping process (e.g., CAPTCHA, Too Many Requests, Network disconnect)."""
    
    error_code = "GOOGLE_MAPS_BLOCKED"

    def __init__(self, reason: str, cause: Exception | None = None) -> None:
        super().__init__(
            f"Google Maps đã chặn hoặc từ chối kết nối. Nguyên nhân: {reason}. "
            "Vui lòng đổi IP (bật/tắt 4G, dùng VPN) hoặc thử lại sau."
        )
        self.reason = reason
        if cause:
            self.__cause__ = cause
