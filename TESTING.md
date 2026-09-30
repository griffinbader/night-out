# Test group: setup and reading the results

## One-time setup

In Supabase, open **SQL Editor → New snippet**, paste everything in `supabase/testing.sql`, and click **Run**.
You should see "Success. No rows returned." Until this runs, visits aren't logged and the report buttons show an error.

## Personal links

Send each person a link with their name (`r=`) and your invite code (`i=`):

```
https://shindig.show/?r=alex&i=YOURCODE
```

Get YOURCODE from Friends → Invite friends (it's the part after `#invite=`). The name after `r=` is only for you. Use first names or anything you'll recognize.
Both stay in the address on purpose: if they add shindig to their iPhone home screen from that page, the home-screen app keeps the name and the invite.

## Reading the results

Open **SQL Editor → New snippet**, paste a query, click **Run**.

**Who came back** (one row per phone or browser):

```sql
select
  coalesce(max(p.display_name), max(v.ref), 'unknown ' || left(v.device_id, 6)) as who,
  max(v.ref) as link,
  bool_or(coalesce(v.installed, false)) as home_screen,
  count(distinct (v.visited_at at time zone 'America/New_York')::date) as days_visited,
  count(*) as visits,
  min(v.visited_at at time zone 'America/New_York') as first_visit,
  max(v.visited_at at time zone 'America/New_York') as last_visit
from visits v
left join profiles p on p.id = v.user_id
group by v.device_id
order by last_visit desc;
```

**Visits per day:**

```sql
select (visited_at at time zone 'America/New_York')::date as day,
       count(distinct device_id) as people, count(*) as visits
from visits group by 1 order by 1 desc;
```

**Wrong or missing show reports** (newest first). You can also browse these in **Table Editor → reports**:

```sql
select created_at at time zone 'America/New_York' as sent, kind, show_label, details
from reports order by created_at desc;
```

`kind` is one of: `wrong_info`, `not_artist`, `cancelled`, `other`, `missing`.

Someone who uses Shindig on two devices (phone and laptop) shows up as two rows unless they sign in on both.
