-- Rollback for migration 015
ALTER VIEW portfolio_summary RESET (security_invoker);
ALTER TABLE health_check DISABLE ROW LEVEL SECURITY;

ALTER FUNCTION set_updated_at()                      RESET search_path;
ALTER FUNCTION create_default_user_settings()        RESET search_path;
ALTER FUNCTION prevent_log_mutation()                RESET search_path;
ALTER FUNCTION calculate_portfolio_stats(uuid)       RESET search_path;
ALTER FUNCTION alpha_block_destructive()             RESET search_path;
ALTER FUNCTION alpha_limit_bulk_delete()             RESET search_path;
