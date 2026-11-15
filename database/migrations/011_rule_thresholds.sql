-- 011: user-configurable rule thresholds (FR-830).
-- Holds only the values the user changed; anything missing uses the documented default
-- (backend/app/domain/thresholds.py validates keys and ranges).
BEGIN;
ALTER TABLE user_settings
    ADD COLUMN IF NOT EXISTS thresholds JSONB NOT NULL DEFAULT '{}'::jsonb;
COMMIT;
