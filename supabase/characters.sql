-- shindig: characters (emoji avatars) instead of colors.
-- Paste into Supabase → SQL Editor → New snippet → Run. Safe to re-run.
alter table public.profiles add column if not exists avatar text check (char_length(avatar) <= 16);
-- profiles only exposes listed columns (invites.sql keeps invite codes private), so allow this one too.
grant select (avatar) on public.profiles to authenticated;
