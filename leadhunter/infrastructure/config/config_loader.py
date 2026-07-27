"""Configuration loader — Infrastructure layer (REQ-069, REQ-070).

Loads, validates, and provides application configuration from YAML files.
Configuration errors abort startup with clear messages (REQ-070).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent.parent / "config" / "default_config.yaml"
_DEFAULT_SCORING_RULES_PATH = Path(__file__).parent.parent.parent.parent / "config" / "scoring_rules.yaml"


@dataclass
class IngestionConfig:
    """Configuration for ingestion operations."""

    max_file_size_mb: float = 50.0
    max_urls_per_run: int = 500
    http_timeout_seconds: float = 10.0
    retry_max_attempts: int = 3
    rate_limit_delay_seconds: float = 1.0
    cache_ttl_hours: float = 24.0


@dataclass
class QueryConfig:
    """Configuration for query/search operations."""

    default_page_size: int = 20
    max_page_size: int = 200


@dataclass
class ScoringConfig:
    """Configuration for scoring operations."""

    batch_size: int = 500


@dataclass
class ExportConfig:
    """Configuration for export operations."""

    batch_size: int = 10000
    output_dir: str = "exports"


@dataclass
class DatabaseConfig:
    """Configuration for SQLite database."""

    path: str = "data/leadhunter.db"
    wal_mode: bool = True


@dataclass
class LoggingConfig:
    """Configuration for logging."""

    level: str = "INFO"
    file_path: str = "logs/leadhunter.log"
    max_bytes: int = 10 * 1024 * 1024
    backup_count: int = 10


@dataclass
class ProxyConfig:
    """Configuration for proxy settings."""

    server: str = ""
    username: str = ""
    password: str = ""


@dataclass
class SerpApiConfig:
    """Configuration for SerpApi settings."""

    api_key: str = ""


@dataclass
class AppConfig:
    """Top-level application configuration (REQ-069).

    All configurable parameters from the SRS are represented here.
    No hardcoded values in use cases or adapters (REQ-069, ARCH-009).

    Attributes:
        ingestion: Ingestion operation parameters.
        query: Query/search parameters.
        scoring: Scoring parameters.
        export: Export parameters.
        database: Database connection parameters.
        logging: Logging parameters.
        proxy: Proxy configuration parameters.
        serpapi: SerpApi configuration parameters.
        actor: Default actor name for audit logs.
    """

    ingestion: IngestionConfig = field(default_factory=IngestionConfig)
    query: QueryConfig = field(default_factory=QueryConfig)
    scoring: ScoringConfig = field(default_factory=ScoringConfig)
    export: ExportConfig = field(default_factory=ExportConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    proxy: ProxyConfig = field(default_factory=ProxyConfig)
    serpapi: SerpApiConfig = field(default_factory=SerpApiConfig)
    actor: str = "cli"


def load_config(
    config_path: str | Path | None = None,
    env_overrides: dict[str, Any] | None = None,
) -> AppConfig:
    """Load and validate application configuration from YAML file (REQ-069, REQ-070).

    Merges default config with optional file overrides.
    Aborts with clear error messages on invalid values (REQ-070).

    Args:
        config_path: Path to a YAML config file. Uses default_config.yaml if None.
        env_overrides: Dictionary of configuration overrides (e.g. from env vars).

    Returns:
        Validated AppConfig instance.

    Raises:
        SystemExit: If the configuration is invalid (REQ-070).
    """
    path = Path(config_path) if config_path else _DEFAULT_CONFIG_PATH

    raw: dict[str, Any] = {}
    if path.exists():
        try:
            with open(str(path), encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
        except Exception as exc:
            _abort(f"Failed to read configuration file '{path}': {exc}")
    else:
        logger.warning(
            "Configuration file not found, using defaults",
            extra={"context": {"path": str(path)}},
        )

    if env_overrides:
        _deep_merge(raw, env_overrides)

    config = _build_config(raw)
    _validate_config(config)
    return config


def load_scoring_rules(rules_path: str | Path | None = None) -> list[dict[str, Any]]:
    """Load scoring rules from a YAML file (REQ-055).

    Args:
        rules_path: Path to scoring_rules.yaml. Uses default if None.

    Returns:
        List of rule dictionaries.

    Raises:
        SystemExit: If the file is invalid (REQ-070).
    """
    path = Path(rules_path) if rules_path else _DEFAULT_SCORING_RULES_PATH

    if not path.exists():
        logger.warning(
            "Scoring rules file not found, using empty ruleset",
            extra={"context": {"path": str(path)}},
        )
        return []

    try:
        with open(str(path), encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception as exc:
        _abort(f"Failed to read scoring rules file '{path}': {exc}")
        return []  # unreachable but satisfies type checker

    return data.get("rules", [])


def _build_config(raw: dict[str, Any]) -> AppConfig:
    """Build AppConfig from raw dictionary.

    Args:
        raw: Raw YAML-loaded dictionary.

    Returns:
        AppConfig instance.
    """
    def get(section: str, key: str, default: Any) -> Any:
        return raw.get(section, {}).get(key, default)

    return AppConfig(
        ingestion=IngestionConfig(
            max_file_size_mb=get("ingestion", "max_file_size_mb", 50.0),
            max_urls_per_run=get("ingestion", "max_urls_per_run", 500),
            http_timeout_seconds=get("ingestion", "http_timeout_seconds", 10.0),
            retry_max_attempts=get("ingestion", "retry_max_attempts", 3),
            rate_limit_delay_seconds=get("ingestion", "rate_limit_delay_seconds", 1.0),
            cache_ttl_hours=get("ingestion", "cache_ttl_hours", 24.0),
        ),
        query=QueryConfig(
            default_page_size=get("query", "default_page_size", 20),
            max_page_size=get("query", "max_page_size", 200),
        ),
        scoring=ScoringConfig(
            batch_size=get("scoring", "batch_size", 500),
        ),
        export=ExportConfig(
            batch_size=get("export", "batch_size", 10000),
            output_dir=get("export", "output_dir", "exports"),
        ),
        database=DatabaseConfig(
            path=get("database", "path", "data/leadhunter.db"),
            wal_mode=get("database", "wal_mode", True),
        ),
        logging=LoggingConfig(
            level=get("logging", "level", "INFO"),
            file_path=get("logging", "file_path", "logs/leadhunter.log"),
            max_bytes=get("logging", "max_bytes", 10 * 1024 * 1024),
            backup_count=get("logging", "backup_count", 10),
        ),
        proxy=ProxyConfig(
            server=get("proxy", "server", ""),
            username=get("proxy", "username", ""),
            password=get("proxy", "password", ""),
        ),
        serpapi=SerpApiConfig(
            api_key=get("serpapi", "api_key", ""),
        ),
        actor=raw.get("actor", "cli"),
    )


def _validate_config(config: AppConfig) -> None:
    """Validate configuration values are within acceptable ranges (REQ-070).

    Args:
        config: AppConfig to validate.

    Raises:
        SystemExit: On any invalid value.
    """
    errors: list[str] = []

    if config.ingestion.max_file_size_mb <= 0:
        errors.append("ingestion.max_file_size_mb must be > 0")
    if config.ingestion.http_timeout_seconds <= 0:
        errors.append("ingestion.http_timeout_seconds must be > 0")
    if config.ingestion.retry_max_attempts < 0:
        errors.append("ingestion.retry_max_attempts must be >= 0")
    if config.ingestion.rate_limit_delay_seconds < 0:
        errors.append("ingestion.rate_limit_delay_seconds must be >= 0")
    if config.query.default_page_size < 1:
        errors.append("query.default_page_size must be >= 1")
    if config.query.max_page_size < config.query.default_page_size:
        errors.append("query.max_page_size must be >= default_page_size")
    if config.scoring.batch_size < 1:
        errors.append("scoring.batch_size must be >= 1")
    if config.logging.backup_count < 1:
        errors.append("logging.backup_count must be >= 1")
    if config.logging.max_bytes < 1024:
        errors.append("logging.max_bytes must be >= 1024")

    if errors:
        msg = "Configuration errors detected — application cannot start:\n" + "\n".join(
            f"  - {e}" for e in errors
        )
        _abort(msg)


def _deep_merge(base: dict, overrides: dict) -> None:
    """Recursively merge override dict into base dict in place.

    Args:
        base: Base dictionary (modified in place).
        overrides: Override dictionary.
    """
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def _abort(message: str) -> None:
    """Print a clear error message and exit the process (REQ-070).

    Args:
        message: Human-readable error description.
    """
    import sys
    print(f"\nConfiguration Error:\n{message}\n", file=sys.stderr)
    sys.exit(2)
