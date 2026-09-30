# Shindig

Find live music in NYC tonight, this weekend, or whenever — filtered by borough, neighborhood, vibe and genre.
Not a ticketing platform: every show links out to the venue's own ticket page.

**Live:** https://shindig.show/ — listings refresh every morning via GitHub Actions (`.github/workflows/collect.yml`).

## Run it
- Collect fresh listings: `python3 collector/collect.py` (writes `data/shows.js`)
- Preview: `python3 -m http.server 5173`, then open http://localhost:5173

## Layout
- `index.html`, `styles.css`, `app.js` — the app (no build step)
- `data.js` — turns collected listings into what the app shows
- `collector/` — reads each venue's calendar (`venues.py` = venue list, `collect.py` = sources)

## Next up
1. MSG / Radio City / Beacon via the Ticketmaster Discovery API — waiting on a developer key (signup link was broken; emailed devportalinquiry@ticketmaster.com). Reader is written: `src_ticketmaster` + `TICKETMASTER_VENUES` in `collector/venues.py`.
2. Branded sign-in emails (e.g. Resend) + a real domain before sharing widely — Supabase's built-in email is rate-limited.
3. AI tagging for leftovers: genres for the ~11% of shows without one, and an "is this really an artist?" check on new listings.
4. No automatic source yet: Baby's All Right, Nightclub 101 (ticket sites block bots), Nowadays (Resident Advisor only), 99 Scott (no calendar).
5. Link-preview image for shared links.

## Keeping listings clean
Artists only — no parties, themed nights, talks, comedy, kids' shows. Rules in `collector/curate.py`, hand-made calls in `collector/overrides.json`, and each run writes what it removed to `data/dropped.txt`.
