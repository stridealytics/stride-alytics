-- Rollback for migration 016 (drops the stored company name)
BEGIN;
ALTER TABLE weekly_picks DROP COLUMN IF EXISTS company_name;
COMMIT;
