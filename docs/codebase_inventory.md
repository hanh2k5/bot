# 📋 CODEBASE INVENTORY — LEADHUNTER PROJECT

**Ngày lập:** 2026-08-11  
**Trạng thái phân loại:** Complete Repository Scan

---

## 📂 1. PRESENTATION LAYER (GUI & CLI)

| File Path | Category | Classification | Description |
|---|---|---|---|
| `gui_app.py` | GUI Launcher / Server | `ACTIVE` | PyWebView desktop window application launcher and HTTP backend API server. |
| `auto_run.py` | CLI Entrypoint | `ACTIVE` | Command-line execution script for automated scraping campaigns. |
| `leadhunter/presentation/cli/main.py` | CLI Main | `ACTIVE` | Click-based CLI entrypoint definitions. |
| `leadhunter/presentation/cli/factory.py` | CLI Factory | `ACTIVE` | Shared factory for repository and use case instances. |
| `leadhunter/presentation/cli/commands/rollback_cmd.py` | CLI Command | `ACTIVE` | Rollback last auto-run batch command. |
| `web_gui/index.html` | GUI Frontend | `ACTIVE` | Modern dark-mode HTML/CSS/JS frontend dashboard interface. |

---

## ⚙️ 2. APPLICATION LAYER (USE CASES & PORTS)

| File Path | Category | Classification | Description |
|---|---|---|---|
| `leadhunter/application/dtos.py` | Application DTOs | `ACTIVE` | Data transfer objects across application boundaries. |
| `leadhunter/application/ports/lead_repository.py` | Port Interface | `ACTIVE` | Abstract LeadRepository interface. |
| `leadhunter/application/ports/ingestion_source_adapter.py` | Port Interface | `ACTIVE` | Abstract IngestionSourceAdapter port interface. |
| `leadhunter/application/use_cases/auto_run_use_case.py` | Use Case | `ACTIVE` | Core orchestrator for multi-threaded auto-scraping, filtering & dedup. |
| `leadhunter/application/use_cases/export_leads_to_excel.py` | Use Case | `ACTIVE` | Export leads from DB to Excel workbook. |
| `leadhunter/application/use_cases/import_leads_from_file.py` | Use Case | `ACTIVE` | Import leads from external files into repository. |
| `leadhunter/application/use_cases/merge_lead.py` | Use Case | `ACTIVE` | Merge duplicate lead records. |
| `leadhunter/application/use_cases/score_leads.py` | Use Case | `ACTIVE` | Apply rule-based scoring to leads. |
| `leadhunter/application/use_cases/scrape_leads_from_urls.py` | Use Case | `ACTIVE` | Scrape leads directly from specific URL targets. |
| `leadhunter/application/use_cases/search_leads.py` | Use Case | `ACTIVE` | Query leads from repository with filtering & pagination. |
| `leadhunter/application/use_cases/update_lead_status.py` | Use Case | `ACTIVE` | Update status and audit trail for a lead. |

---

## 🧠 3. DOMAIN LAYER (ENTITIES, VALUE OBJECTS, SERVICES)

| File Path | Category | Classification | Description |
|---|---|---|---|
| `leadhunter/domain/constants.py` | Domain Constants | `ACTIVE` | Domain constants and enums. |
| `leadhunter/domain/exceptions.py` | Domain Exceptions | `ACTIVE` | Standardized domain exception hierarchy. |
| `leadhunter/domain/entities/lead.py` | Domain Entity | `ACTIVE` | Core Lead domain entity & LeadStatus entity. |
| `leadhunter/domain/services/normalization_service.py` | Domain Service | `ACTIVE` | String normalization services for phone, address, and company name. |
| `leadhunter/domain/services/telecom_service.py` | Domain Service | `ACTIVE` | Carrier detection (Viettel, Vina, Mobi, toll-free, landline 02x). |
| `leadhunter/domain/services/dedup_service.py` | Domain Service | `ACTIVE` | Lead deduplication service logic. |
| `leadhunter/domain/services/scoring_service.py` | Domain Service | `ACTIVE` | Rule-based lead scoring service. |
| `leadhunter/domain/services/status_service.py` | Domain Service | `ACTIVE` | Lead status transition service. |
| `leadhunter/domain/services/auth_service.py` | Domain Service | `ACTIVE` | Authentication and token domain service. |
| `leadhunter/domain/value_objects/phone_number.py` | Value Object | `ACTIVE` | PhoneNumber value object with normalization rules. |
| `leadhunter/domain/value_objects/company_name.py` | Value Object | `ACTIVE` | CompanyName value object. |
| `leadhunter/domain/value_objects/email.py` | Value Object | `ACTIVE` | Email value object with regex validation. |
| `leadhunter/domain/value_objects/website.py` | Value Object | `ACTIVE` | Website value object. |

---

## 🏗️ 4. INFRASTRUCTURE LAYER (ADAPTERS, PERSISTENCE, CONFIG, LOGGING)

| File Path | Category | Classification | Description |
|---|---|---|---|
| `leadhunter/infrastructure/adapters/google_maps_scraper.py` | Adapter | `ACTIVE` | Playwright Google Maps fast scraper adapter. |
| `leadhunter/infrastructure/adapters/maps_utils.py` | Adapter Helper | `ACTIVE` | Helper utilities for Maps scraper parsing. |
| `leadhunter/infrastructure/adapters/excel_writer_adapter.py` | Adapter | `ACTIVE` | OpenPyXL Excel export adapter (5 colored columns). |
| `leadhunter/infrastructure/adapters/excel_reader_adapter.py` | Adapter | `ACTIVE` | OpenPyXL Excel file reader adapter. |
| `leadhunter/infrastructure/adapters/web_scraper_adapter.py` | Adapter | `ACTIVE` | Generic web scraper adapter. |
| `leadhunter/infrastructure/adapters/proxy_rotator.py` | Adapter | `ACTIVE` | Proxy rotation adapter. |
| `leadhunter/infrastructure/config/config_loader.py` | Config Loader | `ACTIVE` | Application configuration & YAML rules loader. |
| `leadhunter/infrastructure/logging/logging_config.py` | Logging | `ACTIVE` | Centralized logging configuration. |
| `leadhunter/infrastructure/logging/json_formatter.py` | Logging | `ACTIVE` | Structured JSON log formatter. |
| `leadhunter/infrastructure/persistence/connection_manager.py` | Persistence | `ACTIVE` | SQLite ConnectionManager thread-safe transaction manager. |
| `leadhunter/infrastructure/persistence/sqlite_lead_repository.py` | Persistence | `ACTIVE` | SqliteLeadRepository SQLite persistence layer with UNIQUE constraint. |
| `leadhunter/infrastructure/persistence/migrations/001_initial_schema.sql` | Migration Script | `ACTIVE` | Initial SQLite schema migration script. |
| `leadhunter/infrastructure/persistence/migrations/002_add_unique_phone_index.sql` | Migration Script | `ACTIVE` | Migration 002 creating `idx_leads_phone_unique` UNIQUE INDEX. |
| `leadhunter/infrastructure/persistence/migrations/migration_runner.py` | Migration Runner | `ACTIVE` | MigrationRunner executing pending SQL migrations in order. |

---

## 🧪 5. TEST SUITE & BENCHMARKS

| File Path | Category | Classification | Description |
|---|---|---|---|
| `tests/conftest.py` | Test Fixture | `TEST ONLY` | Shared pytest fixtures. |
| `tests/unit/test_phase2_regression.py` | Regression Test | `TEST ONLY` | Regression tests for Bugs 1, 2, 4. |
| `tests/unit/test_db_duplicate_protection.py` | Regression Test | `TEST ONLY` | Regression tests for Bug 3 (SQLite UNIQUE index & concurrency). |
| `tests/unit/test_full_suite_features.py` | Unit Test | `TEST ONLY` | Full feature unit test suite. |
| `tests/unit/test_maps_scraper.py` | Unit Test | `TEST ONLY` | Google Maps scraper unit tests. |
| `tests/unit/test_massive_cases.py` | Unit Test | `TEST ONLY` | Parameterized stress tests for normalization & telecom. |
| `tests/unit/test_stress_edge_cases.py` | Unit Test | `TEST ONLY` | Stress & edge case unit tests. |
| `tests/unit/application/test_auto_run_use_case.py` | Unit Test | `TEST ONLY` | AutoRunUseCase unit tests. |
| `tests/unit/domain/test_email.py` | Unit Test | `TEST ONLY` | Email VO unit tests. |
| `tests/unit/domain/test_lead_status.py` | Unit Test | `TEST ONLY` | LeadStatus entity unit tests. |
| `tests/unit/domain/test_normalization_service.py` | Unit Test | `TEST ONLY` | Normalization service unit tests. |
| `tests/unit/domain/test_scoring_service.py` | Unit Test | `TEST ONLY` | Scoring service unit tests. |
| `tests/unit/domain/test_telecom_service.py` | Unit Test | `TEST ONLY` | Telecom service unit tests. |
| `tests/integration/test_migration_runner.py` | Integration Test | `TEST ONLY` | Migration runner integration tests. |
| `tests/integration/test_sqlite_repository.py` | Integration Test | `TEST ONLY` | SqliteLeadRepository integration tests. |

---

## 🛠️ 6. CONFIGURATION, SCRIPTS & ASSETS

| File Path | Category | Classification | Description |
|---|---|---|---|
| `config/config.yaml` | Application Config | `ACTIVE` | Core application settings (database path, limits, logging). |
| `config/scoring_rules.yaml` | Scoring Config | `ACTIVE` | Scoring rule definitions. |
| `pyproject.toml` | Build Config | `ACTIVE` | Python package and pytest settings. |
| `requirements.txt` / `requirements-dev.txt` | Dependencies | `ACTIVE` | Production and development dependency specifications. |
| `setup.sh` / `setup.bat` | Setup Script | `ACTIVE` | Environment setup shell/batch scripts. |
