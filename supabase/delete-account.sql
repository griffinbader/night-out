-- Shindig: let people permanently delete their own account.
-- Paste into Supabase → SQL Editor → New snippet → Run. Safe to re-run.
-- Deleting the sign-in record cascades to the profile, plans and friend connections.

create or replace function public.delete_my_account()
returns void language plpgsql security definer set search_path = public, auth as $$
begin
  if auth.uid() is null then raise exception 'not signed in'; end if;
  delete from auth.users where id = auth.uid();
end $$;

revoke execute on function public.delete_my_account() from anon, public;
grant execute on function public.delete_my_account() to authenticated;
