# Architecture and Configuration Context

This reference was moved verbatim from `CLAUDE.md` to keep long context out of the default instructions. Consult only the relevant section when needed.

## Architecture

**Alpha pipeline** (`alpha/app/main.py:run_system`):
1. Load data: Supabase first (`utils/load_data.py`), then `alpha/raw_screener.csv`, then built-in sample rows.
2. Score options 0–9 (`screener/compute_option_score.py`).
3. Assign bands A–E (`screener/band_pipeline.py`).
4. Apply daily filters (`screener/apply_filters.py`).
5. Build the weekly watchlist (`screener/weekly_watchlist.py`).
6. Write to Supabase (`database/insert_daily.py:sync_day`). It never wipes: it inserts new tickers and updates only changed rows for the day. The ticker list is kept once in `ticker_universe` (`database/universe.py`; the daily sync adds new tickers and soft-removes dropped ones, with a guard against mass removal), and after the first complete load `database/safety.py` blocks bulk deletes (`clear_all_tables`, `delete_rows`) unless `ALPHA_UNLOCK_DESTRUCTIVE=I-UNDERSTAND`.
7. Push to Google Sheets (`sheets/push_to_sheets.py`).

Failures in the insert and Sheets steps only log a warning.

`app/ingest.py` fetches free yfinance metrics through `data_sources/free_metrics.py` (key-free; used first when `INGEST_LIVE=1`). The Polygon, FMP and Massive modules in `data_sources/` are not used by it. `alpha/app/streamlit_app.py` reads Supabase tables with `st.cache_data`. The root `requirements.txt` mirrors alpha's dependencies for Streamlit Cloud.

**Persistence** (`backend/app`): endpoints use `Repo` (`repositories/sql.py`) through `get_ctx` in `api/deps.py`, which resolves the user, creates their `public.users` row on first sight and scopes every query to them. PostgreSQL is used when `DATABASE_URL` is set; otherwise an in-memory SQLite fallback starts (data lost on restart, warning logged). The ORM models define the SQLite schema and the `.sql` files in `database/migrations/` are the PostgreSQL source of truth, so change both together. `signal_log` and `audit_events` are append-only (DB trigger + `ImmutableRecordError`); every trade, portfolio, watchlist and settings change writes an audit row in the same transaction. Alpha's `trades` / `audit_log` tables have different columns than the backend's (see `docs/TODO/PENDING-WORK.md`).

**Trading rules** (`backend/app/domain`, pure functions, no web/DB imports): `regime_score` (0–100 from trend, VIX, IV rank), `allocation` (Base/Growth split, Growth lock), `sizing` (risk budget, quantity, band caps) and `gate` (the Do-Not-Trade rules BR-010–021, including the correlation rule BR-013 fed by an injected `get_returns_provider`), plus `alerts` (exit alerts), `portfolio_risk`, `ev` and `strategy_matrix`. Their limits are not hard-coded: `thresholds.py` holds the defaults, allowed ranges and the user's overrides (`user_settings.thresholds`), and each rule takes a `limits` argument. Scenario repricing lives in `services/scenarios.py`. Live prices, sectors and option chains come from injected providers (`get_position_data_provider`, `get_sector_provider`, `get_chain_provider`), which tests replace with fakes in `tests/conftest.py`. `services/trading.py` loads a user's settings and the live inputs and calls them; `POST /trades` runs the gate and answers 409 with every reason when blocked. **Missing data blocks a trade** (fail-safe) and there is no override. Market data for the gate and regime is injected (`get_symbol_data_provider`, `regime_score.fetch_inputs`), so tests use fakes (see `tests/conftest.py`) and never touch the network. The scheduler imports `app.domain.regime_score` directly, so keep that module free of heavy imports.

**Platform**: the frontend (axios in `src/api/client.ts`, TanStack Query hooks, zustand stores) calls the backend `/api/v1` routes. The backend layers are endpoints → services → models/database, on Supabase Postgres via async SQLAlchemy, with JWT auth. The `scheduler/` scripts write to Supabase on GitHub Actions cron.

## Configuration

- Alpha (`alpha/app/config.py`): `SUPABASE_URL` and `SUPABASE_KEY` (service_role) are required. `POLYGON_API_KEY`, `FMP_API_KEY`, `DASHBOARD_PASSWORD` (Streamlit gate), `MASSIVE_API_KEY`, `GOOGLE_SERVICE_ACCOUNT_JSON`, `GOOGLE_SHEETS_SPREADSHEET_ID` and the Slack/Discord webhook URLs are optional. The alpha README says to copy `alpha/.env.example`, but that file is not tracked.
- Root and `backend/` `.env.example` cover the backend, frontend and mobile settings.
- Backend `ENVIRONMENT` defaults to `production`. Dev auth tokens (`dev:<id>`, `dev-admin-token`) and the dev login fallback work only with `ENVIRONMENT=development` (set it in `backend/.env` for local work). Real Supabase JWTs are verified with audience `authenticated` (`SUPABASE_JWT_AUDIENCE`).
- `ALLOW_SIGNUP` (default false) gates `/auth/signup`; production refuses to start without `DATABASE_URL`; use the Supabase transaction-pooler URL. Auth accepts HS256 (`SUPABASE_JWT_SECRET`) and ES256/RS256 (JWKS from `SUPABASE_URL`). `scheduler/` scripts reuse single `backend/app` modules (`app.services` re-exports nothing on purpose) and `scheduler/tests` guards that they import; weekday jobs run in `market-close.yml`, weekly picks (a copy of alpha's latest `weekly_watchlist` into `weekly_picks`; alpha owns the pick rules) and `prune_data.py` in `weekly.yml`.
- API responses for market tickers, the screener and regime carry a `source` field; anything other than `live` is placeholder data and the UI labels it.
