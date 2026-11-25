-- 015: security hardening flagged by the Supabase advisors after applying 001-014.
--
--  * portfolio_summary was a SECURITY DEFINER view: it ran with the owner's rights and bypassed RLS,
--    so anyone holding the public anon key could read every user's portfolio totals.
--    security_invoker makes it respect the caller's RLS. The backend connects as the database
--    owner, so its behaviour does not change.
--  * health_check had no RLS and was open to the anon key. RLS with no policy denies anon and
--    authenticated users; the backend (owner) and service_role still bypass it.
--  * pin search_path on the functions so a caller cannot shadow objects they reference.
-- Down: 015_security_hardening_down.sql
-- Risk:  low; no data is touched.

-- Assumes the backend's DATABASE_URL role owns the tables or has BYPASSRLS (Supabase's `postgres`
-- role does). A role subject to RLS would see only its own rows through portfolio_summary.
-- Needs PostgreSQL 15+ for security_invoker (Supabase and docker-compose run 15+).
BEGIN;

ALTER VIEW portfolio_summary SET (security_invoker = true);

ALTER TABLE health_check ENABLE ROW LEVEL SECURITY;

ALTER FUNCTION set_updated_at()                      SET search_path = public, pg_temp;
ALTER FUNCTION create_default_user_settings()        SET search_path = public, pg_temp;
ALTER FUNCTION prevent_log_mutation()                SET search_path = public, pg_temp;
ALTER FUNCTION calculate_portfolio_stats(uuid)       SET search_path = public, pg_temp;
ALTER FUNCTION alpha_block_destructive()             SET search_path = public, pg_temp;
ALTER FUNCTION alpha_limit_bulk_delete()             SET search_path = public, pg_temp;

COMMIT;
