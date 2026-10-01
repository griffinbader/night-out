-- shindig: private plans. A plan marked private is only visible to you, never to friends.
-- Paste into Supabase → SQL Editor → New snippet → Run. Safe to re-run.

alter table public.plans add column if not exists private boolean not null default false;
-- Account setting: new plans start private.
alter table public.profiles add column if not exists plans_private boolean not null default false;

drop policy if exists "see own and friends' plans" on public.plans;
create policy "see own and friends' plans" on public.plans
  for select to authenticated
  using (user_id = auth.uid() or (not private and public.are_friends(auth.uid(), user_id)));

-- profiles only exposes listed columns (invites.sql keeps invite codes private), so allow this one too.
grant select (plans_private) on public.profiles to authenticated;
