# Finish setting up accounts (two steps in Supabase)

Project: https://supabase.com/dashboard/project/ieguinuslxfspuhxfaiq

## Step 1 — Run the setup script
1. Left sidebar → **SQL Editor** → **New query**
2. Paste the whole contents of `supabase/schema.sql`
3. Click **Run** → you should see "Success. No rows returned."

## Step 2 — Sign-in link destinations
1. Left sidebar → **Authentication** → **URL Configuration**
2. **Site URL:** `https://shindig.show/`
3. **Redirect URLs** → Add URL, one at a time:
   - `https://shindig.show/`
   - `https://www.shindig.show/`
   - `https://griffinbader.github.io/night-out/`
   - `http://localhost:5173/`
4. **Save**

Then tell Claude "both done" — it will publish accounts to the live site and walk through a test sign-in.
