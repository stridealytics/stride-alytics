-- 012: expected value recorded on a trade when it is opened (FR-920).
-- NULL for trades without a score (stock, long options, back-dated entries, missing inputs).
BEGIN;
ALTER TABLE trades
    ADD COLUMN IF NOT EXISTS entry_ev NUMERIC(12, 2);
COMMIT;
