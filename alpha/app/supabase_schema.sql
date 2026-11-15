-- Alpha Option Trading System — Supabase Schema
-- Create all tables required for ingestion, scoring, bands, trades, watchlist, and audit logs.

-- ─────────────────────────────────────────────
-- 1. daily_metrics — Raw daily ingestion data
-- ─────────────────────────────────────────────
create table if not exists daily_metrics (
    id bigint generated always as identity primary key,
    date text not null,
    ticker text not null,

    -- CSV columns (in order)
    price numeric,
    avg_volume_shares numeric,
    option_volume numeric,
    max_oi_near_exp numeric,
    bid_ask_spread_pct numeric,
    iv_30d numeric,
    iv_rank_1y numeric,
    hv_30d numeric,
    atr numeric,
    next_earnings_date text,
    short_interest_pct numeric,
    revenue_growth_yoy numeric,
    debt_equity numeric,
    quality_score numeric,
    sector text,

    -- computed fields
    option_score numeric,
    band text,
    trend text,
    strategy text,

    inserted_at timestamp default now()
);

-- Columns the pipeline writes but the first version of this table lacked.
alter table daily_metrics add column if not exists market_cap numeric;
alter table daily_metrics add column if not exists beta numeric;
alter table daily_metrics add column if not exists float_shares numeric;

create index if not exists idx_daily_metrics_ticker on daily_metrics(ticker);
create index if not exists idx_daily_metrics_date on daily_metrics(date);


-- ─────────────────────────────────────────────
-- 2. option_scores — Daily scoring results
-- ─────────────────────────────────────────────
create table if not exists option_scores (
    id bigint generated always as identity primary key,
    date text not null,
    ticker text not null,
    option_score numeric,
    trend text,
    strategy text,
    inserted_at timestamp default now()
);

create index if not exists idx_option_scores_ticker on option_scores(ticker);
create index if not exists idx_option_scores_date on option_scores(date);


-- ─────────────────────────────────────────────
-- 3. bands — Daily band classification (A–E)
-- ─────────────────────────────────────────────
create table if not exists bands (
    id bigint generated always as identity primary key,
    date text not null,
    ticker text not null,
    band text,
    inserted_at timestamp default now()
);

create index if not exists idx_bands_ticker on bands(ticker);
create index if not exists idx_bands_date on bands(date);


-- ─────────────────────────────────────────────
-- 4. weekly_watchlist — Weekly top picks
-- ─────────────────────────────────────────────
create table if not exists weekly_watchlist (
    id bigint generated always as identity primary key,
    date text not null,
    ticker text not null,
    sector text,
    price numeric,
    option_score numeric,
    iv_rank_1y numeric,
    iv_30d numeric,
    next_earnings_date text,
    trend text,
    strategy text,
    inserted_at timestamp default now()
);

create index if not exists idx_weekly_watchlist_ticker on weekly_watchlist(ticker);
create index if not exists idx_weekly_watchlist_date on weekly_watchlist(date);


-- ─────────────────────────────────────────────
-- 5. alpha_trades — Trade log (named alpha_* so it cannot clash with the backend's trades table)
-- ─────────────────────────────────────────────
create table if not exists alpha_trades (
    id bigint generated always as identity primary key,
    date text not null,
    ticker text not null,
    strategy text,
    entry_strikes text,
    expiry text,
    credit_debit numeric,
    reason text,
    exit_plan text,
    inserted_at timestamp default now()
);

create index if not exists idx_alpha_trades_ticker on alpha_trades(ticker);
create index if not exists idx_alpha_trades_date on alpha_trades(date);


-- ─────────────────────────────────────────────
-- 6. alpha_audit_log — System events (named alpha_* to avoid the backend's tables)
-- ─────────────────────────────────────────────
create table if not exists alpha_audit_log (
    id bigint generated always as identity primary key,
    timestamp text not null,
    event text not null
);

create index if not exists idx_alpha_audit_log_timestamp on alpha_audit_log(timestamp);


-- ─────────────────────────────────────────────
-- 7. ticker_universe — one row per ticker, loaded once
--    The daily run adds new tickers and marks dropped ones status='removed'.
--    Rows are never deleted or overwritten.
-- ─────────────────────────────────────────────
create table if not exists ticker_universe (
    ticker text primary key,
    sector text,
    source text,
    status text not null default 'active' check (status in ('active', 'removed')),
    added_at timestamptz not null default now(),
    removed_at timestamptz
);

create index if not exists idx_ticker_universe_status on ticker_universe(status);


-- ─────────────────────────────────────────────
-- 8. alpha_state — protection flags
--    After the first complete load, alpha sets initial_load_complete=true and
--    refuses bulk deletes (see app/database/safety.py).
-- ─────────────────────────────────────────────
create table if not exists alpha_state (
    key text primary key,
    value text not null,
    updated_at timestamptz not null default now()
);


-- ─────────────────────────────────────────────
-- 9. Optional, once, after removing duplicate (date, ticker) rows:
--    stops duplicates at the database level. The pipeline already avoids creating them.
--
--    -- find them first (or run alpha/scripts/dedupe_duplicates.sql, which also removes them):
--    --   select date, ticker, count(*) from daily_metrics group by 1, 2 having count(*) > 1;
--    -- then, once clean:
--    --   create unique index if not exists uq_daily_metrics_date_ticker on daily_metrics(date, ticker);
--    (same for option_scores, bands, weekly_watchlist)
-- ─────────────────────────────────────────────


-- ─────────────────────────────────────────────
-- 10. Row-level security (REQUIRED)
--     These tables are in `public`, so Supabase exposes them to the public anon key.
--     RLS with no policies denies anon/authenticated access; alpha, the scheduler and the
--     Streamlit app use the service_role key, which bypasses RLS. Also applied by
--     database/migrations/013_alpha_rls_and_numeric_widen.sql.
-- ─────────────────────────────────────────────
alter table daily_metrics    enable row level security;
alter table option_scores    enable row level security;
alter table bands            enable row level security;
alter table weekly_watchlist enable row level security;
alter table alpha_trades     enable row level security;
alter table alpha_audit_log  enable row level security;
alter table ticker_universe  enable row level security;
alter table alpha_state      enable row level security;
