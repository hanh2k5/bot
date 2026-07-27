"""CLI shared factory — builds use case instances from config."""

from __future__ import annotations

from leadhunter.infrastructure.config.config_loader import AppConfig
from leadhunter.infrastructure.persistence.connection_manager import ConnectionManager
from leadhunter.infrastructure.persistence.sqlite_lead_repository import SqliteLeadRepository
from leadhunter.infrastructure.persistence.migrations.migration_runner import MigrationRunner
from leadhunter.infrastructure.adapters.excel_reader_adapter import ExcelReaderAdapter
from leadhunter.infrastructure.adapters.csv_reader_adapter import CsvReaderAdapter
from leadhunter.infrastructure.adapters.web_scraper_adapter import WebScraperAdapter
from leadhunter.infrastructure.adapters.excel_writer_adapter import ExcelWriterAdapter
from leadhunter.domain.services.scoring_service import ScoringRule, ScoringRules
from leadhunter.infrastructure.config.config_loader import load_scoring_rules


def make_repository(config: AppConfig) -> SqliteLeadRepository:
    """Create and return a configured SqliteLeadRepository.

    Runs migrations automatically if needed.

    Args:
        config: Application configuration.

    Returns:
        Ready-to-use SqliteLeadRepository.
    """
    cm = ConnectionManager(config.database.path)
    # Run pending migrations
    runner = MigrationRunner(cm)
    runner.run()
    return SqliteLeadRepository(cm)


def make_scoring_rules(rules_path: str | None = None) -> ScoringRules:
    """Load scoring rules from YAML configuration.

    Args:
        rules_path: Optional path to scoring_rules.yaml.

    Returns:
        ScoringRules instance.
    """
    raw_rules = load_scoring_rules(rules_path)
    rules = [
        ScoringRule(
            field=r.get("field", ""),
            condition=r.get("condition", ""),
            points=r.get("points", 0),
            weight=r.get("weight", 0),
        )
        for r in raw_rules
    ]
    return ScoringRules(rules=rules)
