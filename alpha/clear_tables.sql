-- Adds the columns the pipeline writes, if they are missing. Safe to re-run.
-- This file used to TRUNCATE every table; that was removed so no one wipes the data by accident.
-- To reset a brand-new database on purpose, use `uv run python reset_and_run.py` (it is blocked
-- once the initial load is complete unless ALPHA_UNLOCK_DESTRUCTIVE=I-UNDERSTAND is set).

ALTER TABLE daily_metrics ADD COLUMN IF NOT EXISTS avg_volume_shares numeric;
ALTER TABLE daily_metrics ADD COLUMN IF NOT EXISTS short_interest_pct numeric;
ALTER TABLE daily_metrics ADD COLUMN IF NOT EXISTS market_cap numeric;
ALTER TABLE daily_metrics ADD COLUMN IF NOT EXISTS beta numeric;
ALTER TABLE daily_metrics ADD COLUMN IF NOT EXISTS float_shares numeric;
ALTER TABLE daily_metrics ADD COLUMN IF NOT EXISTS option_score numeric;
ALTER TABLE daily_metrics ADD COLUMN IF NOT EXISTS band text;
ALTER TABLE daily_metrics ADD COLUMN IF NOT EXISTS trend text;
ALTER TABLE daily_metrics ADD COLUMN IF NOT EXISTS strategy text;
