-- 014: database-level guard so no run, script or mistake can wipe alpha's data.
--
-- The alpha code already only adds, updates and soft-removes (alpha/app/database/safety.py,
-- universe.py). That protection lives in application code, and the service_role key bypasses RLS,
-- so a bug, a wrong script or a pasted SQL statement could still empty a table. These triggers
-- enforce the same rule inside Postgres:
--
--   ticker_universe, alpha_state   no DELETE and no TRUNCATE at all (the code soft-removes, and
--                                   alpha_state holds the "initial load complete" flag).
--   daily_metrics, option_scores,  no TRUNCATE; a single DELETE statement may not remove more than
--   bands, weekly_watchlist        50% of the table once it removes 25 or more rows. Normal runs
--                                   (a few per-ticker deletes, the weekly retention prune) pass.
--
-- Deliberate override, only from the SQL editor (a REST client cannot set this):
--     BEGIN;
--     SET LOCAL alpha.allow_bulk_delete = 'on';
--     DELETE FROM ...;   -- or TRUNCATE ...
--     COMMIT;
--
-- This guards against mistakes, not against someone with superuser rights, who can still drop a
-- trigger or the table. Keep backups (see .github/workflows/database-backup.yml).
-- Guarded so it is safe if alpha's schema was never applied.
BEGIN;

CREATE OR REPLACE FUNCTION alpha_block_destructive()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF current_setting('alpha.allow_bulk_delete', true) = 'on' THEN
        RETURN NULL;
    END IF;
    RAISE EXCEPTION '% on % is blocked: this table is never emptied or hard-deleted by a run. '
        'To do it on purpose, run in the SQL editor: SET LOCAL alpha.allow_bulk_delete = ''on''.',
        TG_OP, TG_TABLE_NAME
        USING ERRCODE = 'integrity_constraint_violation';
END;
$$;

CREATE OR REPLACE FUNCTION alpha_limit_bulk_delete()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    removed   bigint;
    remaining bigint;
BEGIN
    IF current_setting('alpha.allow_bulk_delete', true) = 'on' THEN
        RETURN NULL;
    END IF;
    SELECT count(*) INTO removed FROM deleted;
    EXECUTE format('SELECT count(*) FROM %I.%I', TG_TABLE_SCHEMA, TG_TABLE_NAME) INTO remaining;
    IF removed >= 25 AND removed * 2 > removed + remaining THEN
        RAISE EXCEPTION 'DELETE on % blocked: it would remove % of % rows (limit 50%%). '
            'To do it on purpose, run in the SQL editor: SET LOCAL alpha.allow_bulk_delete = ''on''.',
            TG_TABLE_NAME, removed, removed + remaining
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    RETURN NULL;
END;
$$;

DO $$
DECLARE
    t text;
BEGIN
    -- never emptied, never hard-deleted
    FOREACH t IN ARRAY ARRAY['ticker_universe', 'alpha_state']
    LOOP
        IF to_regclass('public.' || t) IS NOT NULL THEN
            EXECUTE format('DROP TRIGGER IF EXISTS trg_%s_no_delete ON public.%I', t, t);
            EXECUTE format(
                'CREATE TRIGGER trg_%s_no_delete BEFORE DELETE ON public.%I '
                'FOR EACH STATEMENT EXECUTE FUNCTION alpha_block_destructive()', t, t);
            EXECUTE format('DROP TRIGGER IF EXISTS trg_%s_no_truncate ON public.%I', t, t);
            EXECUTE format(
                'CREATE TRIGGER trg_%s_no_truncate BEFORE TRUNCATE ON public.%I '
                'FOR EACH STATEMENT EXECUTE FUNCTION alpha_block_destructive()', t, t);
        END IF;
    END LOOP;

    -- a few rows may go (per-ticker drops, retention prune); the whole table may not
    FOREACH t IN ARRAY ARRAY['daily_metrics', 'option_scores', 'bands', 'weekly_watchlist']
    LOOP
        IF to_regclass('public.' || t) IS NOT NULL THEN
            EXECUTE format('DROP TRIGGER IF EXISTS trg_%s_no_truncate ON public.%I', t, t);
            EXECUTE format(
                'CREATE TRIGGER trg_%s_no_truncate BEFORE TRUNCATE ON public.%I '
                'FOR EACH STATEMENT EXECUTE FUNCTION alpha_block_destructive()', t, t);
            EXECUTE format('DROP TRIGGER IF EXISTS trg_%s_limit_delete ON public.%I', t, t);
            EXECUTE format(
                'CREATE TRIGGER trg_%s_limit_delete AFTER DELETE ON public.%I '
                'REFERENCING OLD TABLE AS deleted '
                'FOR EACH STATEMENT EXECUTE FUNCTION alpha_limit_bulk_delete()', t, t);
        END IF;
    END LOOP;
END
$$;

COMMIT;
