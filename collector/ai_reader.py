"""AI reader: for venues whose calendar isn't on a platform we have a reader for, open the page in a
real browser, then have Claude pull the shows out of the page text.

Runs only where both Playwright and an Anthropic API key are available (the GitHub Action once the
ANTHROPIC_API_KEY secret is added). Each page's text is fingerprinted, and Claude is only called when
the page has changed since the last run; otherwise the saved result is reused.
"""

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "ai_cache.json"
NYC = ZoneInfo("America/New_York")
MODEL = "claude-opus-5-5"

# Venue calendar pages the AI reader handles (no official feed or readable platform found for these).
AI_PAGES = {
    "citywinery": "https://citywinery.com/nyc",
    "pioneerworks": "https://pioneerworks.org/programs",
    "unitedpalace": "https://unitedpalaceevents.com/",
    "crownhill": "https://crownhilltheatre.com/calendar",
    "storehouse": "https://brooklynstorehouse.com/events/",
    "monarch": "https://www.brooklynmonarch.com/",
    "pacha": "https://www.pachanyc.com/",
    "tveye": "https://tveyenyc.com/",
    "knockdown": "https://knockdown.center/",
}

SCHEMA = {
    "type": "object",
    "properties": {
        "events": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "headliner": {"type": "string"},
                    "support": {"type": "array", "items": {"type": "string"}},
                    "date": {"type": "string", "description": "YYYY-MM-DD"},
                    "time": {"type": "string", "description": "24h HH:MM show time, or empty if not shown"},
                    "ticket_url": {"type": "string", "description": "absolute URL, or empty"},
                    "base_price": {"type": "string", "description": "lowest price before fees as a number like 25, or empty"},
                    "is_music": {"type": "boolean"},
                },
                "required": ["headliner", "support", "date", "time", "ticket_url", "base_price", "is_music"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["events"],
    "additionalProperties": False,
}

INSTRUCTIONS = """You are extracting upcoming events from a New York music venue's calendar page.
Venue: {venue}
Today's date: {today}

List every upcoming event on the page. For each one:
- headliner: the main billed artist, band or DJ exactly as written (drop words like "An Evening with", tour names, "SOLD OUT", age limits).
- support: other billed artists, if any.
- date: YYYY-MM-DD. The page may omit the year; pick the next occurrence on or after today.
- time: show time (or doors if that's all there is) in 24h HH:MM, or "" if not shown.
- ticket_url: the event's ticket or info link from the LINKS list, or "".
- base_price: the lowest ticket price before fees if printed, like "25"; "" if not shown or only an all-in price.
- is_music: true only for live music or DJ sets with a named artist. False for comedy, talks, readings, parties or themed nights with no named artist, classes, private events, film screenings, markets.
Only include events that actually appear on the page. Never invent events or details."""


def available():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False, "no ANTHROPIC_API_KEY — AI reader off"
    try:
        import anthropic  # noqa: F401
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError:
        return False, "anthropic / playwright not installed here (runs in GitHub Actions)"
    return True, ""


def _render(url, user_agent):
    """Page text plus its links, as a visitor's browser would see them."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(user_agent=user_agent)
        page.goto(url, wait_until="networkidle", timeout=90000)
        page.wait_for_timeout(2500)
        text = page.inner_text("body")
        links = page.eval_on_selector_all("a[href]", "els => els.map(a => [a.innerText.trim().slice(0, 80), a.href])")
        browser.close()
    seen, lines = set(), []
    for label, href in links:
        if href.startswith("http") and href not in seen:
            seen.add(href)
            lines.append(f"{label} | {href}")
    return text, "\n".join(lines[:400])


def _extract(venue_name, text, links):
    import anthropic
    client = anthropic.Anthropic()
    prompt = INSTRUCTIONS.format(venue=venue_name, today=datetime.now(NYC).strftime("%Y-%m-%d"))
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",  # if a request is declined, the API finishes it on a fallback model
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": f"{prompt}\n\nPAGE TEXT:\n{text}\n\nLINKS (label | url):\n{links}"}],
    )
    if response.stop_reason in ("refusal", "max_tokens"):
        raise RuntimeError(f"AI reader stopped early ({response.stop_reason})")
    raw = next(b.text for b in response.content if b.type == "text")
    return json.loads(raw)["events"]


def read_venues(venues_by_id, user_agent, log=print):
    """Returns (events, report_lines). Each event is a dict ready for collect.show()."""
    ok, why = available()
    if not ok:
        return [], [f"  – AI reader: {why}"]
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    out, report = [], []
    for vid, url in AI_PAGES.items():
        venue = venues_by_id.get(vid)
        if not venue:
            continue
        try:
            text, links = _render(url, user_agent)
            if len(text.strip()) < 200:
                report.append(f"  ✗ AI reader: {venue['name']}: page looks empty or blocked")
                continue
            fingerprint = hashlib.sha256((text + links).encode()).hexdigest()
            hit = cache.get(vid)
            if hit and hit.get("fingerprint") == fingerprint:
                events, note = hit["events"], "unchanged, reused"
            else:
                events, note = _extract(venue["name"], text, links), "read by Claude"
                cache[vid] = {"fingerprint": fingerprint, "events": events, "read_at": datetime.now(NYC).isoformat()}
            music = [e for e in events if e.get("is_music")]
            for e in music:
                e["venue"] = vid
            out += music
            report.append(f"  ✓ AI reader: {venue['name']}: {len(music)} shows ({note})")
        except Exception as e:  # one bad page shouldn't stop the rest
            report.append(f"  ✗ AI reader: {venue['name']}: {type(e).__name__}: {e}")
    CACHE.parent.mkdir(exist_ok=True)
    CACHE.write_text(json.dumps(cache, indent=1))
    return out, report
