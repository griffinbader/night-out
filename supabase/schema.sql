-- Night Out database: profiles, plans (going / interested / history), friends.
-- Paste this whole file into Supabase → SQL Editor → New query → Run. Safe to re-run.

-- ---------------------------------------------------------------- profiles
create table if not exists public.profiles (
  id          uuid primary key references auth.users (id) on delete cascade,
  username    text unique not null check (username ~ '^[a-z0-9_]{3,20}$'),
  display_name text not null check (char_length(display_name) between 1 and 40),
  color       text not null default '#ffd23f' check (color ~ '^#[0-9a-fA-F]{6}$'),
  created_at  timestamptz not null default now()
);

-- ---------------------------------------------------------------- plans
-- One row per person per show. "show" keeps a copy of the listing (artist,
-- venue, start…) so history still works after a show leaves the listings.
create table if not exists public.plans (
  user_id    uuid not null references public.profiles (id) on delete cascade,
  show_id    text not null check (char_length(show_id) <= 200),
  status     text not null check (status in ('going', 'interested')),
  show       jsonb not null default '{}'::jsonb,
  show_start timestamptz,
  updated_at timestamptz not null default now(),
  primary key (user_id, show_id)
);
create index if not exists plans_show_idx on public.plans (show_id);

-- ---------------------------------------------------------------- friends
-- "follower adds followee". Two people are friends once both have added each other.
create table if not exists public.follows (
  follower_id uuid not null references public.profiles (id) on delete cascade,
  followee_id uuid not null references public.profiles (id) on delete cascade,
  created_at  timestamptz not null default now(),
  primary key (follower_id, followee_id),
  check (follower_id <> followee_id)
);
create index if not exists follows_followee_idx on public.follows (followee_id);

create or replace function public.are_friends(a uuid, b uuid)
returns boolean language sql stable security definer set search_path = public as $$
  select exists (select 1 from follows where follower_id = a and followee_id = b)
     and exists (select 1 from follows where follower_id = b and followee_id = a);
$$;

-- ---------------------------------------------------------------- privacy rules
alter table public.profiles enable row level security;
alter table public.plans    enable row level security;
alter table public.follows  enable row level security;

-- Profiles: signed-in people can look each other up by username (to add friends).
drop policy if exists "profiles readable by signed-in users" on public.profiles;
create policy "profiles readable by signed-in users" on public.profiles
  for select to authenticated using (true);
drop policy if exists "create own profile" on public.profiles;
create policy "create own profile" on public.profiles
  for insert to authenticated with check (id = auth.uid());
drop policy if exists "edit own profile" on public.profiles;
create policy "edit own profile" on public.profiles
  for update to authenticated using (id = auth.uid()) with check (id = auth.uid());

-- Plans: you see your own, plus your friends' (mutual adds only). You only edit your own.
drop policy if exists "see own and friends' plans" on public.plans;
create policy "see own and friends' plans" on public.plans
  for select to authenticated
  using (user_id = auth.uid() or public.are_friends(auth.uid(), user_id));
drop policy if exists "add own plans" on public.plans;
create policy "add own plans" on public.plans
  for insert to authenticated with check (user_id = auth.uid());
drop policy if exists "change own plans" on public.plans;
create policy "change own plans" on public.plans
  for update to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());
drop policy if exists "remove own plans" on public.plans;
create policy "remove own plans" on public.plans
  for delete to authenticated using (user_id = auth.uid());

-- Follows: you see adds that involve you; you can only add/remove your own.
drop policy if exists "see follows involving me" on public.follows;
create policy "see follows involving me" on public.follows
  for select to authenticated using (follower_id = auth.uid() or followee_id = auth.uid());
drop policy if exists "add own follows" on public.follows;
create policy "add own follows" on public.follows
  for insert to authenticated with check (follower_id = auth.uid());
drop policy if exists "remove own follows" on public.follows;
create policy "remove own follows" on public.follows
  for delete to authenticated using (follower_id = auth.uid());
