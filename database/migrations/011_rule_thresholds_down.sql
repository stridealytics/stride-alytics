-- Rollback for migration 011 (drops the saved rule thresholds)
BEGIN;
ALTER TABLE user_settings DROP COLUMN IF EXISTS thresholds;
COMMIT;
