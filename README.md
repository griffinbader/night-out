# Shindig

Find live music in NYC tonight, this weekend, or whenever — filtered by borough, neighborhood, vibe and genre.
Not a ticketing platform: every show links out to the venue's own ticket page.

**Live:** https://griffinbader.github.io/night-out/ — listings refresh every morning via GitHub Actions (`.github/workflows/collect.yml`).

## Run it
- Collect fresh listings: `python3 collector/collect.py` (writes `data/shows.js`)
- Preview: `python3 -m http.server 5173`, then open http://localhost:5173

## Layout
- `index.html`, `styles.css`, `app.js` — the app (no build step)
- `data.js` — turns collected listings into what the app shows
- `collector/` — reads each venue's calendar (`venues.py` = venue list, `collect.py` = sources)

## Next up
1. AI genre tagging for the ~25% of shows MusicBrainz/Last.fm don't know
2. Accounts so friends / "Going" are real (friends are sample data for now)
3. Find a source for Baby's All Right and Nightclub 101 (their ticket sites block automated visitors)
