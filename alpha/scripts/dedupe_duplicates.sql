-- Remove duplicate (date, ticker) rows from the alpha tables, then add unique indexes.
-- Run in the Supabase SQL editor, ONE STEP AT A TIME. It deletes only the surplus copies
-- (the newest row per day and ticker is kept) and first saves what it will delete.
-- Dates stored with a time part (2026-11-14T10:00:00) count as the same day as 2026-11-14.

-- ───── STEP 1: preview (read-only). Note the numbers. ─────
select 'daily_metrics' as table_name, count(*) as surplus_rows from (
  select id, row_number() over (partition by left(date, 10), ticker order by id desc) as rn from daily_metrics
) x where rn > 1;
select 'option_scores' as table_name, count(*) as surplus_rows from (
  select id, row_number() over (partition by left(date, 10), ticker order by id desc) as rn from option_scores
) x where rn > 1;
select 'bands' as table_name, count(*) as surplus_rows from (
  select id, row_number() over (partition by left(date, 10), ticker order by id desc) as rn from bands
) x where rn > 1;
select 'weekly_watchlist' as table_name, count(*) as surplus_rows from (
  select id, row_number() over (partition by left(date, 10), ticker order by id desc) as rn from weekly_watchlist
) x where rn > 1;

-- ───── STEP 2: save the surplus rows, then delete them (one transaction). ─────
begin;

create table if not exists dup_backup_daily_metrics as select * from daily_metrics where false;
insert into dup_backup_daily_metrics
  select * from daily_metrics where id in (
    select id from (
      select id, row_number() over (partition by left(date, 10), ticker order by id desc) as rn from daily_metrics
    ) x where rn > 1);
delete from daily_metrics where id in (select id from dup_backup_daily_metrics);

create table if not exists dup_backup_option_scores as select * from option_scores where false;
insert into dup_backup_option_scores
  select * from option_scores where id in (
    select id from (
      select id, row_number() over (partition by left(date, 10), ticker order by id desc) as rn from option_scores
    ) x where rn > 1);
delete from option_scores where id in (select id from dup_backup_option_scores);

create table if not exists dup_backup_bands as select * from bands where false;
insert into dup_backup_bands
  select * from bands where id in (
    select id from (
      select id, row_number() over (partition by left(date, 10), ticker order by id desc) as rn from bands
    ) x where rn > 1);
delete from bands where id in (select id from dup_backup_bands);

create table if not exists dup_backup_weekly_watchlist as select * from weekly_watchlist where false;
insert into dup_backup_weekly_watchlist
  select * from weekly_watchlist where id in (
    select id from (
      select id, row_number() over (partition by left(date, 10), ticker order by id desc) as rn from weekly_watchlist
    ) x where rn > 1);
delete from weekly_watchlist where id in (select id from dup_backup_weekly_watchlist);

-- Check the counts below against STEP 1, then COMMIT (or ROLLBACK to undo everything).
select 'daily_metrics' as table_name, (select count(*) from dup_backup_daily_metrics) as saved, (select count(*) from daily_metrics) as remaining;
select 'option_scores' as table_name, (select count(*) from dup_backup_option_scores) as saved, (select count(*) from option_scores) as remaining;
select 'bands' as table_name, (select count(*) from dup_backup_bands) as saved, (select count(*) from bands) as remaining;
select 'weekly_watchlist' as table_name, (select count(*) from dup_backup_weekly_watchlist) as saved, (select count(*) from weekly_watchlist) as remaining;
commit;

-- ───── STEP 3: store every date as a plain YYYY-MM-DD, then forbid duplicates. ─────
begin;
update daily_metrics set date = left(date, 10) where length(date) > 10;
update option_scores set date = left(date, 10) where length(date) > 10;
update bands set date = left(date, 10) where length(date) > 10;
update weekly_watchlist set date = left(date, 10) where length(date) > 10;
create unique index if not exists uq_daily_metrics_date_ticker on daily_metrics(date, ticker);
create unique index if not exists uq_option_scores_date_ticker on option_scores(date, ticker);
create unique index if not exists uq_bands_date_ticker on bands(date, ticker);
create unique index if not exists uq_weekly_watchlist_date_ticker on weekly_watchlist(date, ticker);
commit;

-- ───── STEP 4 (later, once you are happy): drop the saved copies. ─────
-- drop table dup_backup_daily_metrics, dup_backup_option_scores, dup_backup_bands, dup_backup_weekly_watchlist;
