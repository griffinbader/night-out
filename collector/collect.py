"""Shindig collector: gathers upcoming shows from venue websites.

Run:  python3 collector/collect.py
Writes data/shows.js, which the app loads. Past shows from earlier runs are kept
(for people's show history). One request per calendar page, respecting robots.txt.
"""

import gzip
import os
import html
import json
import re
import sys
import urllib.parse
import urllib.request
import urllib.robotparser
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent))
from genres import tag_shows  # noqa: E402
from venues import BOWERY_NAMES, TICKETMASTER_VENUES, VENUES  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "shows.js"
NYC = ZoneInfo("America/New_York")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
DAYS_AHEAD = 90
KEEP_PAST_DAYS = 400

# ---------------------------------------------------------------- fetching

_robots = {}


def allowed(url):
    host = "{0.scheme}://{0.netloc}".format(urlparse(url))
    if host not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            req = urllib.request.Request(host + "/robots.txt", headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=15) as r:
                rp.parse(r.read().decode("utf-8", "ignore").splitlines())
        except Exception:
            rp.parse([])  # no robots.txt -> everything allowed
        _robots[host] = rp
    return _robots[host].can_fetch("*", url)


def fetch(url):
    if not allowed(url):
        raise RuntimeError(f"robots.txt disallows {url}")
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            body = gzip.decompress(body)
    return body.decode("utf-8", "ignore")


# ---------------------------------------------------------------- helpers

def text(s):
    """Strip tags + decode entities + collapse whitespace."""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def clean_title(t):
    t = re.sub(r"\*[^*]{1,30}\*", "", t)  # *SOLD OUT*, *NEW DATE* …
    t = re.sub(r"\b(SOLD OUT|POSTPONED|RESCHEDULED|CANCELL?ED)\b[:!\s-]*", "", t)  # all-caps status words only
    t = re.sub(r"^\s*NEW[:!-]\s*", "", t)
    t = re.sub(r"\s+@\s+[^@]+$", "", t)  # "Artist @ Market Hotel"
    return re.sub(r"\s+", " ", t).strip(" -–|")


def split_lineup(title, commas=False):
    """'A • B • C' / 'A + B' / 'A w/ B' -> ('A', ['B', 'C']).

    commas=True also splits 'A, B' — only for small-venue calendars, since big
    acts like 'Earth, Wind & Fire' would get chopped up.
    """
    sep = r"\s+(?:•|\+|w/|with|/)\s+|\s*•\s*" + (r"|,\s+" if commas else "")
    parts = re.split(sep, title)
    parts = [p.strip() for p in parts if p.strip()]
    return (parts[0], parts[1:]) if parts else (title, [])


PRESENTER = re.compile(r"(presents?|series|showcase|salon|residency|night|nights|party)\s*:?$", re.I)


def split_tagline(name):
    """'Artist: The Big Tour' -> ('Artist', 'The Big Tour');
    'LPR Presents: Artist' -> ('Artist', 'LPR Presents')."""
    for sep in (": ", " - ", " – ", " — "):
        if sep in name:
            a, b = (x.strip() for x in name.split(sep, 1))
            if PRESENTER.search(a) and b:
                return b, a
            if len(a) > 1:
                return a, b
    m = re.match(r"(.{3,60}?)\s+presents?\s+(.+)", name, re.I)
    if m:
        return m.group(2).strip(), m.group(1).strip() + " presents"
    return name, ""


def price_num(v):
    if v is None:
        return None
    m = re.search(r"\d+(?:\.\d+)?", str(v).replace(",", ""))
    return round(float(m.group())) if m else None


def local_iso(dt_str):
    """Any ISO datetime -> NYC local 'YYYY-MM-DDTHH:MM'."""
    dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    if dt.tzinfo:
        dt = dt.astimezone(NYC)
    return dt.strftime("%Y-%m-%dT%H:%M")


def parse_clock(s):
    m = re.search(r"(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m", s or "", re.I)
    if not m:
        return None
    h = int(m.group(1)) % 12 + (12 if m.group(3).lower() == "p" else 0)
    return f"{h:02d}:{m.group(2) or '00'}"


def show(venue, artist, start, support=(), tagline="", price=None, image=None, url=None, genres=(), source=""):
    artist, tl = split_tagline(clean_title(artist))
    return dict(
        venue=venue, artist=artist, support=[s for s in support if s and s != artist][:6],
        tagline=tagline or tl, start=start, price=price, image=image, url=url,
        genres=list(genres)[:3], source=source,
    )


def jsonld_events(page):
    """Every schema.org *Event object found in a page's JSON-LD."""
    found = []

    def walk(o):
        if isinstance(o, dict):
            if "Event" in str(o.get("@type", "")) and o.get("startDate"):
                found.append(o)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    for block in re.findall(r"<script[^>]*application/ld\+json[^>]*>(.*?)</script>", page, re.S):
        try:
            walk(json.loads(block))
        except ValueError:
            pass
    return found


# ---------------------------------------------------------------- sources

def src_jsonld(url, venue):
    """Ticketmaster/Live Nation venue sites and DICE venue pages."""
    out = []
    for e in jsonld_events(fetch(url)):
        name = text(e.get("name", ""))
        head, support = split_lineup(clean_title(name), commas="dice.fm" in url)
        offers = e.get("offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        img = e.get("image")
        img = img[0] if isinstance(img, list) and img else img
        out.append(show(venue, head, local_iso(e["startDate"]), support, price=price_num(offers.get("lowPrice") or offers.get("price")),
                        image=img, url=e.get("url"), source="jsonld"))
    return out


def src_bowery_presents():
    """One feed covering Bowery Presents' NYC venues (Webster Hall, Brooklyn Steel, Racket, ...)."""
    data = json.loads(fetch("https://aegwebprod.blob.core.windows.net/json/events/59/events.json"))
    out = []
    for e in data["events"]:
        venue = BOWERY_NAMES.get((e.get("venue") or {}).get("title"))
        if not venue or not e.get("active", True):
            continue
        t = e.get("title") or {}
        head = t.get("headlinersText") or t.get("eventTitleText") or ""
        support = [s.strip() for s in re.split(r",\s*|\s+/\s+", t.get("supportingText") or "") if s.strip()]
        media = e.get("media") or {}
        img = (media.get("17") or media.get("1") or next(iter(media.values()), {}) or {}).get("file_name")
        price = price_num(e.get("ticketPrice")) or price_num(e.get("ticketPriceLow")) or None
        out.append(show(venue, head, e["eventDateTime"][:16], support, tagline=t.get("tour") or "",
                        price=price, image=img, url=(e.get("ticketing") or {}).get("url"), source="bowery"))
    return out


def src_mercury_east(url, venue):
    """Bowery Ballroom + Mercury Lounge (TicketWeb WordPress calendar)."""
    out = []
    for block in fetch(url).split('<div class="tw-section">')[1:]:
        name = re.search(r'<div class="tw-name">\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.S)
        date = re.search(r'tw-event-date">([^<]+)<', block)
        if not (name and date):
            continue
        times = re.findall(r'tw-event-time">([^<]+)<', block)
        clock = parse_clock(times[-1] if times else "") or "20:00"
        day = datetime.strptime(date.group(1).strip(), "%a %b %d, %Y").strftime("%Y-%m-%d")
        support = re.findall(r"<span>([^<]+)</span>", (re.search(r'tw-attractions">(.*?)</div>', block, re.S) or [None, ""])[1] or "")
        img = re.search(r'<img[^>]*class="event-img[^"]*"[^>]*src="([^"]+)"', block) or re.search(r'<img[^>]*src="([^"]+)"', block)
        price = re.search(r'tw-price">([^<]+)<', block)
        head, extra = split_lineup(clean_title(text(name.group(2))), commas=True)
        out.append(show(venue, head, f"{day}T{clock}", extra + [text(s) for s in support],
                        price=price_num(price.group(1)) if price else None,
                        image=img.group(1) if img else None, url=name.group(1), source="mercuryeast"))
    return out


def src_lpr():
    out = []
    for block in re.split(r'<div class="event event_', fetch("https://lpr.com/"))[1:]:
        name = re.search(r'class="black_visible">(.*?)</span>', block, re.S)
        date = re.search(r"<span class='date'>([^<]+)</span>", block)
        if not (name and date):
            continue
        d = re.sub(r"(\d)(st|nd|rd|th)", r"\1", date.group(1).strip())
        day = datetime.strptime(d, "%a %B %d, %Y").strftime("%Y-%m-%d")
        clock = parse_clock((re.search(r"<span class='time'>([^<]+)</span>", block) or [None, ""])[1]) or "19:00"
        img = re.search(r"background-image:url\(([^)]+)\)", block)
        link = re.search(r'class="eventSingleLink" href="([^"]+)"', block)
        presenters = re.search(r"<h4 class='presenters[^']*'>(.*?)</h4>", block, re.S)
        head, support = split_lineup(text(name.group(1)), commas=True)
        out.append(show("lpr", head, f"{day}T{clock}", support, tagline=text(presenters.group(1)) if presenters else "",
                        image=img.group(1) if img else None, url=link.group(1) if link else None, source="lpr"))
    return out


def src_elsewhere():
    page = fetch("https://www.elsewhere.club/events")
    data = json.loads(re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', page, re.S).group(1))
    out = []
    for e in data["props"]["pageProps"]["initialEventData"]["events"]:
        artists = e.get("artists") or [e.get("name")]
        cents = e.get("representative_ticket_price")
        imgs = e.get("image_urls") or []
        img = imgs[0] if imgs else None  # signed URLs: must be used exactly as given
        out.append(show("elsewhere", artists[0], local_iso(e["start_date"]), artists[1:],
                        price=round(int(cents) / 100) if cents else None, image=img,
                        url=e.get("ticket_url"), genres=e.get("genres") or [], source="elsewhere"))
    return out


SKIP_BOWL = re.compile(r"closed|private event|family bowl|screening|brunch|trivia|add[ -]on|bowling lane|not a concert ticket", re.I)


def src_brooklyn_bowl():
    out = []
    for block in fetch("https://www.brooklynbowl.com/brooklyn/shows/all").split('<div class="eventItem')[1:]:
        title = re.search(r'<h3 class="title[^"]*">\s*<a href="([^"]+)"[^>]*>(.*?)</a>', block, re.S)
        date = re.search(r'aria-label="([A-Z][a-z]+\s+\d+\s+\d{4})"', block)
        tagline = re.search(r'<h4 class="tagline">(.*?)</h4>', block, re.S)
        if not (title and date) or SKIP_BOWL.search(text(title.group(2)) + " " + text(tagline.group(1) if tagline else "")):
            continue
        day = datetime.strptime(re.sub(r"\s+", " ", date.group(1)), "%B %d %Y").strftime("%Y-%m-%d")
        tm = re.search(r'<div class="time">(.*?)</div>', block, re.S)
        tm = text(tm.group(1)) if tm else ""
        clock = parse_clock(tm.split("Show:")[-1]) or parse_clock(tm) or "20:00"
        img = re.search(r'<img src="([^"]+)"', block)
        img = img.group(1) if img and "default_thumb" not in img.group(1) else None
        btn = text((re.search(r'<div class="buttons">(.*?)</div>\s*</div>', block, re.S) or [None, ""])[1] or "")
        price = 0 if re.search(r"free|no cover", btn, re.I) else None
        support = [s.strip() for s in text(tagline.group(1)).split(",")] if tagline else []
        out.append(show("bowl", text(title.group(2)), f"{day}T{clock}", support, price=price,
                        image=img, url=title.group(1), source="brooklynbowl"))
    return out


def src_venuepilot(account_id, venue):
    """Venues using the VenuePilot calendar widget (Market Hotel)."""
    q = ("query($a:[Int!]!,$s:String!,$l:Int){publicEvents(accountIds:$a,startDate:$s,limit:$l)"
         "{id name date doorTime startTime support ticketsUrl status images}}")
    body = json.dumps({"query": q, "variables": {"a": [account_id], "s": datetime.now(NYC).strftime("%Y-%m-%d"), "l": 200}}).encode()
    req = urllib.request.Request("https://www.venuepilot.co/graphql", data=body,
                                 headers={"User-Agent": UA, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        events = json.load(r)["data"]["publicEvents"]
    out = []
    for e in events:
        if (e.get("status") or "").lower() in ("cancelled", "canceled", "postponed"):
            continue
        head, support = split_lineup(clean_title(e["name"]), commas=True)
        support += [x.strip() for x in re.split(r",|\n", e.get("support") or "") if x.strip()]
        clock = (e.get("startTime") or e.get("doorTime") or "20:00")[:5]
        imgs = e.get("images") or []
        out.append(show(venue, head, f"{e['date']}T{clock}", support, image=imgs[0] if imgs else None,
                        url=e.get("ticketsUrl"), source="venuepilot"))
    return out


def src_seetickets_wp(url, venue):
    """Venue sites using the See Tickets WordPress plugin (TV Eye) — read from the venue's own page."""
    now = datetime.now(NYC)
    out = []
    for block in re.split(r'<div[^>]*class="[^"]*seetickets-list-event-container', fetch(url))[1:]:
        title = re.search(r'class="[^"]*\btitle"><a href="([^"]+)"[^>]*>(.*?)</a>', block, re.S)
        date = re.search(r'class="[^"]*\bdate">([^<]+)<', block)
        if not (title and date):
            continue
        day = datetime.strptime(f"{date.group(1).strip()} {now.year}", "%a %b %d %Y")
        if day.date() < (now - timedelta(days=30)).date():  # "Jan 3" seen in December = next year
            day = day.replace(year=now.year + 1)
        clock = parse_clock((re.search(r'see-showtime[^>]*>([^<]+)<', block) or [None, ""])[1]) or "20:00"
        support = text((re.search(r'supporting-talent">(.*?)</p>', block, re.S) or [None, ""])[1])
        support = [x.strip() for x in re.split(r",|\band\b", re.sub(r"^with\s+", "", support, flags=re.I)) if x.strip()]
        price = re.search(r'class="price">([^<]+)<', block)
        genre = text((re.search(r'class="fs-12 genre">(.*?)</p>', block, re.S) or [None, ""])[1])
        img = re.search(r'<img[^>]*src="([^"]+)"', block)
        head, extra = split_lineup(clean_title(text(title.group(2))), commas=True)
        out.append(show(venue, head, f"{day:%Y-%m-%d}T{clock}", extra + support, price=price_num(price.group(1)) if price else None,
                        image=img.group(1) if img else None, url=title.group(1), genres=[genre] if genre else [],
                        source="seetickets-wp"))
    return out


def src_holo():
    page = fetch("https://h0l0.nyc/events")
    data = json.loads(re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', page, re.S).group(1))["props"]["pageProps"]
    out, seen = [], set()
    for e in (data.get("allUpcomingEvents") or []) + (data.get("highlightedEvents") or []):
        if e["id"] in seen:
            continue
        seen.add(e["id"])
        a = e["attributes"]
        poster = (((a.get("Poster") or {}).get("data") or {}).get("attributes") or {}).get("url")
        head, support = split_lineup(clean_title(a["Title"]), commas=True)
        out.append(show("holo", head, local_iso(a["EventDateTime"]), support, image=poster, url=a.get("Link"), source="holo"))
    return out


def src_national_sawdust():
    out = []
    page = fetch("https://www.nationalsawdust.org/performances")
    grid = page.split('<div data-w-tab="Tab 2"')[0]  # grid view only (list view repeats the same events)
    for item in grid.split('role="listitem"')[1:]:
        link = re.search(r'<a href="(/event/[^"]+)"', item)
        title = re.search(r'article-title-filter-list[^>]*>(.*?)</h4>', item, re.S)
        date = re.search(r'category-title-date[^"]*"[^>]*>([A-Z][a-z]+ \d{1,2}, \d{4})<', item)
        if not (link and title and date):
            continue
        day = datetime.strptime(date.group(1), "%B %d, %Y").strftime("%Y-%m-%d")
        img = re.search(r'background-image:url\(&quot;([^&]+)&quot;\)', item)
        tickets = re.search(r'<a href="(https?://[^"]+)"[^>]*class="button', item)
        out.append(show("sawdust", text(title.group(1)), f"{day}T19:30", image=img.group(1) if img else None,
                        url=tickets.group(1) if tickets else "https://www.nationalsawdust.org" + link.group(1),
                        source="nationalsawdust"))
    return out


SKIP_TM = re.compile(r"parking|suite|premium seat|vip package|upgrade|tour package|hospitality|gift card", re.I)


def src_ticketmaster():
    """Ticketmaster Discovery API (official) — music events only, so no Knicks/Nets/Rangers games."""
    key = os.environ.get("TICKETMASTER_API_KEY") or _env_value("TICKETMASTER_API_KEY")
    if not key:
        raise RuntimeError("no TICKETMASTER_API_KEY yet — skipped")
    out = []
    for tm_id, venue in TICKETMASTER_VENUES.items():
        q = urllib.parse.urlencode({"apikey": key, "venueId": tm_id, "classificationName": "music",
                                    "size": 200, "sort": "date,asc", "countryCode": "US"})
        data = json.loads(fetch("https://app.ticketmaster.com/discovery/v2/events.json?" + q))
        for e in (data.get("_embedded") or {}).get("events", []):
            start = e.get("dates", {}).get("start", {})
            if not start.get("localDate") or SKIP_TM.search(e["name"]) or e.get("dates", {}).get("status", {}).get("code") == "cancelled":
                continue
            acts = [a["name"] for a in (e.get("_embedded") or {}).get("attractions", [])]
            head = acts[0] if acts else e["name"]
            imgs = sorted((i for i in e.get("images", []) if i.get("ratio") == "16_9"), key=lambda i: -i.get("width", 0))
            img = next((i["url"] for i in reversed(imgs) if i.get("width", 0) >= 640), imgs[0]["url"] if imgs else None)
            genres = [c.get(k, {}).get("name", "") for c in e.get("classifications", []) for k in ("genre", "subGenre")]
            price = min((p.get("min") for p in e.get("priceRanges", []) if p.get("min")), default=None)
            out.append(show(venue, head, f"{start['localDate']}T{(start.get('localTime') or '19:30')[:5]}", acts[1:],
                            tagline=e["name"] if e["name"] != head else "", price=round(price) if price else None,
                            image=img, url=e.get("url"),
                            genres=[g for g in genres if g and g.lower() not in ("undefined", "other")], source="ticketmaster"))
    return out


def _env_value(name):
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith(name + "="):
                return line.split("=", 1)[1].strip()
    return None


SOURCES = [
    ("Irving Plaza", lambda: src_jsonld("https://www.irvingplaza.com/", "irving")),
    ("Brooklyn Paramount", lambda: src_jsonld("https://www.brooklynparamount.com/", "paramount")),
    ("Warsaw", lambda: src_jsonld("https://www.warsawconcerts.com/", "warsaw")),
    ("Gramercy Theatre", lambda: src_jsonld("https://www.thegramercytheatre.com/", "gramercy")),
    ("Union Pool (DICE)", lambda: src_jsonld("https://dice.fm/venue/union-pool-nbvl", "unionpool")),
    ("The Sultan Room (DICE)", lambda: src_jsonld("https://dice.fm/venue/the-sultan-room-e27w", "sultan")),
    ("Sultan Room Rooftop (DICE)", lambda: src_jsonld("https://dice.fm/venue/the-sultan-room-rooftop-x57a", "sultanroof")),
    ("Bowery Presents NYC", src_bowery_presents),
    ("Bowery Ballroom", lambda: src_mercury_east("https://mercuryeastpresents.com/boweryballroom/", "bowery")),
    ("Mercury Lounge", lambda: src_mercury_east("https://mercuryeastpresents.com/mercurylounge/", "mercury")),
    ("LPR", src_lpr),
    ("Elsewhere", src_elsewhere),
    ("Brooklyn Bowl", src_brooklyn_bowl),
    ("Public Records (DICE)", lambda: src_jsonld("https://dice.fm/venue/public-records-w2qg", "publicrecords")),
    ("Market Hotel", lambda: src_venuepilot(100, "markethotel")),
    ("TV Eye", lambda: src_seetickets_wp("https://tveyenyc.com/", "tveye")),
    ("H0L0", src_holo),
    ("National Sawdust", src_national_sawdust),
    ("Ticketmaster (MSG, Radio City, Beacon, Barclays, Kings, Sony Hall, Forest Hills)", src_ticketmaster),
]

# ---------------------------------------------------------------- main

# Shindig is for live music — drop the talks, film nights and burlesque that venues also host.
NOT_MUSIC = re.compile(
    r"burlesque|podcast|film tour|film festival|screening|comedy|stand-?up|politics|awards|"
    r"trivia|bingo|book (talk|launch)|in conversation|drag (show|brunch)|wrestling|freeski|yoga|karaoke",
    re.I,
)


VENUE_SIZE = {v["id"]: v["size"] for v in VENUES}
VENUE_GENRE = {v["id"]: v.get("genre") for v in VENUES}


def show_id(s):
    slug = re.sub(r"[^a-z0-9]+", "-", s["artist"].lower()).strip("-")[:40]
    return f"{s['start'][:10]}-{s['venue']}-{slug}"


def load_existing():
    if not OUT.exists():
        return []
    raw = OUT.read_text()
    return json.loads(raw[raw.index("{"):raw.rindex("}") + 1]).get("shows", [])


def main():
    now = datetime.now(NYC)
    today = now.strftime("%Y-%m-%d")
    horizon = (now + timedelta(days=DAYS_AHEAD)).strftime("%Y-%m-%d")
    oldest = (now - timedelta(days=KEEP_PAST_DAYS)).strftime("%Y-%m-%d")

    fresh, report, big_slots = {}, [], set()
    for label, fn in SOURCES:
        try:
            got = [s for s in fn() if today <= s["start"][:10] <= horizon and s["artist"]
                   and not NOT_MUSIC.search(f"{s['artist']} {s['tagline']}")]
            for s in got:
                s["id"] = show_id(s)
                slot = (s["venue"], s["start"])
                if VENUE_SIZE.get(s["venue"]) == "large" and slot in big_slots:
                    continue  # same arena show from a second feed
                big_slots.add(slot)
                fresh.setdefault(s["id"], s)  # first source wins on duplicates
            report.append(f"  ✓ {label}: {len(got)} shows")
        except Exception as e:  # one broken site shouldn't stop the rest
            report.append(f"  ✗ {label}: {type(e).__name__}: {e}")

    print("\n".join(report))
    report = []
    tagged = tag_shows(list(fresh.values()))
    for s in fresh.values():  # club venues: untagged nights are almost always dance music
        if not s["genres"] and VENUE_GENRE.get(s["venue"]):
            s["genres"] = [VENUE_GENRE[s["venue"]]]
    report.append(f"\n  genres: {tagged}/{len(fresh)} shows tagged")

    # keep past shows from earlier runs (history), drop anything stale
    past = [s for s in load_existing() if oldest <= s["start"][:10] < today and s["id"] not in fresh]
    shows = sorted(past + list(fresh.values()), key=lambda s: s["start"])

    OUT.parent.mkdir(exist_ok=True)
    payload = {"updated": now.strftime("%Y-%m-%dT%H:%M"), "venues": VENUES, "shows": shows}
    OUT.write_text("// Generated by collector/collect.py — do not edit by hand.\nwindow.NIGHT_OUT = "
                   + json.dumps(payload, ensure_ascii=False, indent=0) + ";\n")

    print("\n".join(report))
    print(f"\n{len(fresh)} upcoming shows (+{len(past)} past) -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
