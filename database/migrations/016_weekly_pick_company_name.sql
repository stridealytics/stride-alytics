-- 016: company name shown next to the ticker on weekly picks.
-- NULL for picks published before this migration or when the name lookup failed.
BEGIN;
ALTER TABLE weekly_picks
    ADD COLUMN IF NOT EXISTS company_name TEXT;
COMMIT;
