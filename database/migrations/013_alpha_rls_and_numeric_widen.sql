-- 013: (1) lock down alpha's tables with row-level security, (2) widen options Greek columns.
--
-- (1) The alpha pipeline tables live in `public`, so Supabase exposes them through its REST API
--     to anyone holding the public anon key. Enabling RLS with NO policies denies anon and
--     authenticated users; the alpha pipeline, scheduler and Streamlit app use the service_role
--     key, which bypasses RLS. Guarded so it is safe if alpha's schema was never applied.
-- (2) theta / vega / rho were NUMERIC(5,4) (max 9.9999); rho for a high strike or a long expiry
--     can exceed that and the upsert would fail.
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
            EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
        END IF;
    END LOOP;
END
$$;

ALTER TABLE options
    ALTER COLUMN theta TYPE NUMERIC(10, 4),
    ALTER COLUMN vega  TYPE NUMERIC(10, 4),
    ALTER COLUMN rho   TYPE NUMERIC(10, 4);

COMMIT;
