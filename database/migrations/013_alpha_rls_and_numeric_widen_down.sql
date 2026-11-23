-- Rollback for migration 013. Re-narrowing fails if any value is >= 10, which is intended.
BEGIN;
DO $$
DECLARE
    t text;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'daily_metrics', 'option_scores', 'bands', 'weekly_watchlist',
        'ticker_universe', 'alpha_trades', 'alpha_audit_log', 'alpha_state'
    ]
    LOOP
        IF to_regclass('public.' || t) IS NOT NULL THEN
            EXECUTE format('ALTER TABLE public.%I DISABLE ROW LEVEL SECURITY', t);
        END IF;
    END LOOP;
END
$$;
ALTER TABLE options
    ALTER COLUMN theta TYPE NUMERIC(5, 4),
    ALTER COLUMN vega  TYPE NUMERIC(5, 4),
    ALTER COLUMN rho   TYPE NUMERIC(5, 4);
COMMIT;
