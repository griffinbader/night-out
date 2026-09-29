-- Night Out setup, step 2 of 6
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
