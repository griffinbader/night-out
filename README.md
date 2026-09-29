# Night Out

Find live music in NYC tonight, this weekend, or whenever — filtered by borough, neighborhood, vibe and genre.
Not a ticketing platform: every show links out to the venue's own ticket page.

## Run it
- Collect fresh listings: `python3 collector/collect.py` (writes `data/shows.js`)
- Preview: `python3 -m http.server 5173`, then open http://localhost:5173

## Layout
- `index.html`, `styles.css`, `app.js` — the app (no build step)
- `data.js` — turns collected listings into what the app shows
- `collector/` — reads each venue's calendar (`venues.py` = venue list, `collect.py` = sources)

## Next up
1. Genre tagging for every show (only Elsewhere provides genres today)
2. Put it online + run the collector daily
3. Accounts so friends / "Going" are real (friends are sample data for now)
4. Find a source for Baby's All Right and Nightclub 101 (their ticket sites block automated visitors)
