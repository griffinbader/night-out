-- Night Out setup, step 6 of 6
drop policy if exists "profiles readable by signed-in users" on public.profiles;

create policy "profiles readable by signed-in users" on public.profiles
  for select to authenticated using (true);

drop policy if exists "create own profile" on public.profiles;

create policy "create own profile" on public.profiles
  for insert to authenticated with check (id = auth.uid());

drop policy if exists "edit own profile" on public.profiles;

create policy "edit own profile" on public.profiles
  for update to authenticated using (id = auth.uid()) with check (id = auth.uid());

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

drop policy if exists "see follows involving me" on public.follows;

create policy "see follows involving me" on public.follows
  for select to authenticated using (follower_id = auth.uid() or followee_id = auth.uid());

drop policy if exists "add own follows" on public.follows;

create policy "add own follows" on public.follows
  for insert to authenticated with check (follower_id = auth.uid());

drop policy if exists "remove own follows" on public.follows;

create policy "remove own follows" on public.follows
  for delete to authenticated using (follower_id = auth.uid());
