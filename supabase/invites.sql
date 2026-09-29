-- Shindig invite links. Paste into Supabase → SQL Editor → New snippet → Run. Safe to re-run.
-- Everyone gets a secret invite code; opening someone's invite link makes you friends both ways.

alter table public.profiles
  add column if not exists invite_code text unique
  default substr(md5(random()::text || clock_timestamp()::text), 1, 12);
update public.profiles
  set invite_code = substr(md5(random()::text || clock_timestamp()::text || id::text), 1, 12)
  where invite_code is null;

-- Keep invite codes private: other people can see your name/username/color, not your code.
revoke select on public.profiles from authenticated, anon;
grant select (id, username, display_name, color, created_at) on public.profiles to authenticated;

create or replace function public.my_invite_code()
returns text language sql stable security definer set search_path = public as $$
  select invite_code from profiles where id = auth.uid();
$$;

create or replace function public.accept_invite(code text)
returns json language plpgsql security definer set search_path = public as $$
declare inviter profiles%rowtype;
begin
  if auth.uid() is null then raise exception 'not signed in'; end if;
  select * into inviter from profiles where invite_code = code;
  if not found then raise exception 'That invite link isn''t valid.'; end if;
  if inviter.id = auth.uid() then return json_build_object('self', true); end if;
  insert into follows (follower_id, followee_id)
    values (auth.uid(), inviter.id), (inviter.id, auth.uid())
    on conflict do nothing;
  return json_build_object('username', inviter.username, 'display_name', inviter.display_name);
end $$;

revoke execute on function public.my_invite_code() from anon, public;
revoke execute on function public.accept_invite(text) from anon, public;
grant execute on function public.my_invite_code() to authenticated;
grant execute on function public.accept_invite(text) to authenticated;
