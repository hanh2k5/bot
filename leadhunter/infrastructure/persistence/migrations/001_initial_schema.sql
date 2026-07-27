-- Migration 001: Initial schema
-- Applied automatically by MigrationRunner at startup (REQ-033)
-- All tables use explicit column types and FK constraints
-- Indexes created per NFR-012 for search/dedup performance

-- ============================================================
-- Core Lead table
-- ============================================================
CREATE TABLE IF NOT EXISTS leads (
    id                  TEXT        NOT NULL PRIMARY KEY,
    company_name        TEXT        NOT NULL,
    contact_name        TEXT        NOT NULL DEFAULT '',
    email               TEXT        NOT NULL,
    phone               TEXT        NOT NULL DEFAULT '',
    website             TEXT        NOT NULL DEFAULT '',
    address             TEXT        NOT NULL DEFAULT '',
    source              TEXT        NOT NULL,
    source_reference    TEXT        NOT NULL DEFAULT '',
    status              TEXT        NOT NULL DEFAULT 'NEW',
    score               INTEGER     NOT NULL DEFAULT 0
                            CHECK (score >= 0 AND score <= 100),
    notes               TEXT        NOT NULL DEFAULT '',
    created_at          TEXT        NOT NULL,  -- ISO 8601 UTC
    updated_at          TEXT        NOT NULL,  -- ISO 8601 UTC
    import_batch_id     TEXT,
    phone_normalized    INTEGER     NOT NULL DEFAULT 0  -- 0=false, 1=true
);

-- Indexes for REQ-043, REQ-047, REQ-048, NFR-001, NFR-012
CREATE INDEX IF NOT EXISTS idx_leads_email
    ON leads (email);

CREATE INDEX IF NOT EXISTS idx_leads_company_phone
    ON leads (company_name, phone);

CREATE INDEX IF NOT EXISTS idx_leads_status
    ON leads (status);

CREATE INDEX IF NOT EXISTS idx_leads_score
    ON leads (score);

CREATE INDEX IF NOT EXISTS idx_leads_created_at
    ON leads (created_at);

CREATE INDEX IF NOT EXISTS idx_leads_source
    ON leads (source);

-- Full-text search helper columns (covered by regular indexes for LIKE queries)
-- Note: SQLite FTS5 could be added in a future migration for better performance.

-- ============================================================
-- Import history
-- ============================================================
CREATE TABLE IF NOT EXISTS import_history (
    import_batch_id     TEXT        NOT NULL PRIMARY KEY,
    source_file_name    TEXT        NOT NULL,
    executed_at         TEXT        NOT NULL,
    success_count       INTEGER     NOT NULL DEFAULT 0,
    error_count         INTEGER     NOT NULL DEFAULT 0,
    duplicate_count     INTEGER     NOT NULL DEFAULT 0,
    actor               TEXT        NOT NULL DEFAULT 'cli'
);

-- ============================================================
-- Duplicate log (REQ-025)
-- ============================================================
CREATE TABLE IF NOT EXISTS duplicate_log (
    id                  TEXT        NOT NULL PRIMARY KEY,
    original_lead_id    TEXT        NOT NULL REFERENCES leads(id),
    duplicate_data      TEXT        NOT NULL,  -- JSON of raw record
    detected_at         TEXT        NOT NULL,
    import_batch_id     TEXT        NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_duplicate_log_original
    ON duplicate_log (original_lead_id);

-- ============================================================
-- Lead status history (REQ-037)
-- ============================================================
CREATE TABLE IF NOT EXISTS lead_status_history (
    id                  TEXT        NOT NULL PRIMARY KEY,
    lead_id             TEXT        NOT NULL REFERENCES leads(id),
    old_status          TEXT        NOT NULL,
    new_status          TEXT        NOT NULL,
    changed_at          TEXT        NOT NULL,
    actor               TEXT        NOT NULL DEFAULT 'cli',
    reason              TEXT
);

CREATE INDEX IF NOT EXISTS idx_status_history_lead
    ON lead_status_history (lead_id, changed_at);

-- ============================================================
-- Export history (REQ-061)
-- ============================================================
CREATE TABLE IF NOT EXISTS export_history (
    id                  TEXT        NOT NULL PRIMARY KEY,
    executed_at         TEXT        NOT NULL,
    filter_criteria     TEXT        NOT NULL DEFAULT '{}',  -- JSON
    record_count        INTEGER     NOT NULL DEFAULT 0,
    output_file_path    TEXT        NOT NULL DEFAULT '',
    actor               TEXT        NOT NULL DEFAULT 'cli'
);

-- ============================================================
-- Schema migration tracking (REQ-033)
-- ============================================================
CREATE TABLE IF NOT EXISTS schema_migrations (
    version             INTEGER     NOT NULL PRIMARY KEY,
    name                TEXT        NOT NULL,
    applied_at          TEXT        NOT NULL
);
