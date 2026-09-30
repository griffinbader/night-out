-- Shindig: visit log (who comes back) and listing reports (wrong or missing shows).
-- Paste into Supabase → SQL Editor → New snippet → Run. Safe to re-run.
-- The app can only ADD rows to these tables; nobody can read them through the app.
-- You read them in the Supabase dashboard (Table Editor, or the queries in TESTING.md).

-- One row each time someone opens Shindig (at most once every 30 minutes per device).
-- device_id is a random code the browser makes up and keeps; it isn't tied to anything else.
create table if not exists public.visits (
  id bigint generated always as identity primary key,
  device_id text not null check (length(device_id) between 8 and 64),
  user_id uuid default auth.uid() references auth.users on delete cascade,
  ref text check (length(ref) <= 64),
  visited_at timestamptz not null default now()
);
alter table public.visits enable row level security;
drop policy if exists "log a visit" on public.visits;
create policy "log a visit" on public.visits for insert to anon, authenticated
  with check (user_id is null or user_id = auth.uid());

-- "Wrong info on this show" and "Missing a show?" reports.
create table if not exists public.reports (
  id bigint generated always as identity primary key,
  kind text not null check (kind in ('wrong_info', 'not_artist', 'cancelled', 'other', 'missing')),
  show_id text check (length(show_id) <= 200),
  show_label text check (length(show_label) <= 300),
  details text check (length(details) <= 1000),
  device_id text check (length(device_id) <= 64),
  user_id uuid default auth.uid() references auth.users on delete set null,
  created_at timestamptz not null default now()
);
alter table public.reports enable row level security;
drop policy if exists "send a report" on public.reports;
create policy "send a report" on public.reports for insert to anon, authenticated
  with check (user_id is null or user_id = auth.uid());

grant insert on public.visits, public.reports to anon, authenticated;
