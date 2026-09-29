-- Night Out setup, part1-tables.sql
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
