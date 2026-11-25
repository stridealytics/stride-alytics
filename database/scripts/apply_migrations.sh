#!/usr/bin/env bash
# ----------------------------------------------------------------------------
# Apply pending database migrations in order. Usage:
#
#   ./database/scripts/apply_migrations.sh [DATABASE_URL]
#   BASELINE=1 ./database/scripts/apply_migrations.sh [DATABASE_URL]
#
# If DATABASE_URL is omitted, the script falls back to the env var
# DATABASE_URL or the local docker-compose default.
#
# Applied files are recorded in public.schema_migrations and skipped next time.
# BASELINE=1 records every file as applied WITHOUT running it: use it once on a database that
# already has them (for example one migrated through the Supabase MCP or SQL editor).
# ----------------------------------------------------------------------------
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DSN="${1:-${DATABASE_URL:-postgresql://postgres:postgres@localhost:5432/stridealytics}}"

psql "$DSN" -v ON_ERROR_STOP=1 -q -c "
CREATE TABLE IF NOT EXISTS public.schema_migrations (
    filename   TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE public.schema_migrations ENABLE ROW LEVEL SECURITY;"

echo "Applying migrations from $ROOT/database/migrations/"
echo

for f in $(ls "$ROOT/database/migrations/"*.sql | grep -v '_down.sql' | sort); do
    name="$(basename "$f")"
    done_already="$(psql "$DSN" -v ON_ERROR_STOP=1 -tA -c "SELECT 1 FROM public.schema_migrations WHERE filename = '$name'")"
    if [[ -n "$done_already" ]]; then
        echo "  == $name (already applied)"
        continue
    fi
    if [[ "${BASELINE:-}" == "1" ]]; then
        echo "  .. $name (recorded, not run)"
    else
        echo "  -> $name"
        psql "$DSN" -v ON_ERROR_STOP=1 -q -f "$f" >/dev/null
    fi
    psql "$DSN" -v ON_ERROR_STOP=1 -q -c "INSERT INTO public.schema_migrations (filename) VALUES ('$name')"
done

echo
echo "Done."
echo
echo "Verifying schema:"
psql "$DSN" -c "\dt" -c "\dv"
