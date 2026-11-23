-- Rollback for migration 012 (drops the stored entry EV)
BEGIN;
ALTER TABLE trades DROP COLUMN IF EXISTS entry_ev;
COMMIT;
