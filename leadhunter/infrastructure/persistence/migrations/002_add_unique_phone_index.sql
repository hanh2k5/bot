-- Migration 002: Add Unique Index on Phone column to prevent database duplicates
-- Applied automatically by MigrationRunner at startup (REQ-033)

-- 1. Safely remove existing duplicate phone records, keeping the earliest record (smallest ROWID)
DELETE FROM leads
WHERE phone IS NOT NULL AND phone != '' AND ROWID NOT IN (
    SELECT MIN(ROWID)
    FROM leads
    WHERE phone IS NOT NULL AND phone != ''
    GROUP BY phone
);

-- 2. Create UNIQUE index on phone column for non-empty phone strings
CREATE UNIQUE INDEX IF NOT EXISTS idx_leads_phone_unique ON leads(phone) WHERE phone != '' AND phone IS NOT NULL;
