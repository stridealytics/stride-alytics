-- Down for 014: remove the alpha delete guard triggers and functions.
BEGIN;

DO $$
DECLARE
    t text;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'ticker_universe', 'alpha_state',
        'daily_metrics', 'option_scores', 'bands', 'weekly_watchlist'
    ]
    LOOP
        IF to_regclass('public.' || t) IS NOT NULL THEN
            EXECUTE format('DROP TRIGGER IF EXISTS trg_%s_no_delete ON public.%I', t, t);
            EXECUTE format('DROP TRIGGER IF EXISTS trg_%s_no_truncate ON public.%I', t, t);
            EXECUTE format('DROP TRIGGER IF EXISTS trg_%s_limit_delete ON public.%I', t, t);
        END IF;
    END LOOP;
END
$$;

DROP FUNCTION IF EXISTS alpha_block_destructive();
DROP FUNCTION IF EXISTS alpha_limit_bulk_delete();

COMMIT;
