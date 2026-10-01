"""Shindig collector: gathers upcoming shows from venue websites.

Run:  python3 collector/collect.py
Writes data/shows.js, which the app loads. Past shows from earlier runs are kept
(for people's show history). One request per calendar page, respecting robots.txt.
"""

import gzip
import os
import html
import json
import math
import re
import subprocess
import sys
import time
from difflib import SequenceMatcher
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent))
import ai_reader  # noqa: E402
from curate import OVERRIDES, curate  # noqa: E402
from genres import mark_groove, mark_rising, tag_shows  # noqa: E402
from venues import BOWERY_NAMES, IGNORED_CANDIDATES, SEASONAL_VENUES, SEATGEEK_VENUES, TICKETMASTER_VENUES, VENUE_NAMES, VENUE_SITES, VENUES  # noqa: E402

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


def fetch(url, api=False):
    # api=True: an official API we're signed up for with our own key, so crawler rules don't apply
    if not api and not allowed(url):
        raise RuntimeError(f"robots.txt disallows {url}")
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                body = gzip.decompress(body)
    except urllib.error.URLError as e:
        if "SSL" not in str(e):
            raise
        # macOS's built-in Python has an old SSL library some sites refuse; curl doesn't.
        body = subprocess.run(["curl", "-sL", "--compressed", "-m", "30", "-A", UA, url],
                              capture_output=True, check=True).stdout
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


EVENING_WITH = re.compile(r"^(?:an?\s+)?(?:new york\s+|intimate\s+|special\s+|acoustic\s+)?(?:evening|night)\s+(?:of\s+[\w' ]+?\s+)?with\s+", re.I)


def split_lineup(title, commas=False):
    """'A • B • C' / 'A + B' / 'A w/ B' -> ('A', ['B', 'C']).

    commas=True also splits 'A, B' — only for small-venue calendars, since big
    acts like 'Earth, Wind & Fire' would get chopped up.
    """
    # "An Evening with X" names the artist after "with" — handle before splitting on "with"
    title = re.sub(EVENING_WITH, "", title).strip()
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
        if re.search(r"Cancel|Postpon|Reschedul", str(e.get("eventStatus", ""))):
            continue
        where = (e.get("location") or {}).get("name") if isinstance(e.get("location"), dict) else None
        if where and _our_venue(where) != venue:
            VENUE_MISMATCHES.append(f"{name} — page for {venue} says it's at {where!r}; skipped")
            continue
        head, support = split_lineup(clean_title(name), commas="dice.fm" in url)
        offers = e.get("offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        img = e.get("image")
        img = img[0] if isinstance(img, list) and img else img
        # DICE prices include fees and it doesn't publish the base price, so leave those blank
        base = None if "dice.fm" in url else price_num(offers.get("lowPrice") or offers.get("price"))
        out.append(show(venue, head, local_iso(e["startDate"]), support, price=base,
                        image=img, url=e.get("url"), source="jsonld"))
    return out


def src_bowery_presents(account=59, names=None):
    """AEG/AXS venue feeds. Account 59 = Bowery Presents' NYC venues (Webster Hall, Brooklyn Steel,
    Racket, ...); 58 = Forest Hills Stadium, which has its own feed."""
    names = names or BOWERY_NAMES
    data = json.loads(fetch(f"https://aegwebprod.blob.core.windows.net/json/events/{account}/events.json"))
    out = []
    for e in data["events"]:
        venue = names.get((e.get("venue") or {}).get("title"))
        if not venue or not e.get("active", True):
            continue
        t = e.get("title") or {}
        head = t.get("headlinersText") or t.get("eventTitleText") or ""
        if re.search(r"\bmoved\b|cancel|postpone", " ".join(str(v) for v in t.values()) + " " + str(e.get("status", "")), re.I):
            continue  # "Revocation (moved to Saint Vitus)"
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
        price = None
        if link and day >= datetime.now(NYC).strftime("%Y-%m-%d"):
            try:  # LPR prints the base ticket price on each show's page ("Event Ticket: $25")
                m = re.search(r"Event Ticket:\s*\$\s?(\d+)", text(fetch(link.group(1))))
                price = int(m.group(1)) if m else None
            except Exception:
                pass
        out.append(show("lpr", head, f"{day}T{clock}", support, tagline=text(presenters.group(1)) if presenters else "",
                        price=price, image=img.group(1) if img else None, url=link.group(1) if link else None, source="lpr"))
    return out


def src_elsewhere():
    page = fetch("https://www.elsewhere.club/events")
    data = json.loads(re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', page, re.S).group(1))
    out = []
    for e in data["props"]["pageProps"]["initialEventData"]["events"]:
        if not (e.get("address") or "").startswith("599 Johnson"):
            VENUE_MISMATCHES.append(f"{e.get('name')} — Elsewhere feed, but at {e.get('address')!r}; skipped")
            continue
        artists = e.get("artists") or [e.get("name")]
        cents = e.get("representative_ticket_price")
        imgs = e.get("image_urls") or []
        img = imgs[0] if imgs else None  # signed URLs: must be used exactly as given
        rooftop = any("rooftop" in (r or "").lower() for r in e.get("venues") or [])
        out.append(show("elsewhere", artists[0], local_iso(e["start_date"]), artists[1:],
                        price=round(int(cents) / 100) if cents else None, image=img,
                        url=e.get("ticket_url"), genres=e.get("genres") or [], source="elsewhere"))
        if rooftop:
            out[-1]["outdoor"] = True
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


def src_blue_note():
    """Blue Note NYC — residencies are listed as date ranges; one listing per night."""
    out = []
    page = fetch("https://www.bluenotejazz.com/nyc/")
    for li in re.split(r"<li class='show-slide", page)[1:]:
        name = re.search(r"<h3\s*><a href='([^']+)'>(.*?)</a>", li, re.S)
        days = re.findall(r"<time datetime='(\d{4}-\d{2}-\d{2})'", li)
        if not (name and days):
            continue
        first = datetime.strptime(days[0], "%Y-%m-%d")
        last = datetime.strptime(days[-1], "%Y-%m-%d")
        img = re.search(r"data-image='([^']+)'", li)
        head, support = split_lineup(clean_title(text(name.group(2))))
        d = first
        while d <= last and (d - first).days < 14:
            out.append(show("bluenote", head, f"{d:%Y-%m-%d}T20:00", support, image=img.group(1) if img else None,
                            url=name.group(1), genres=["Jazz"], source="bluenote"))
            d += timedelta(days=1)
    return out


def src_palladium():
    out = []
    page = fetch("https://www.palladiumtimessquare.com/")
    for box in page.split('event-list-box port-')[1:]:
        link = re.search(r'<a href="(https://www\.palladiumtimessquare\.com/event/[^"]+)"', box)
        title = re.search(r"<h3[^>]*>\s*<a[^>]*>(.*?)</a>", box, re.S)
        date = re.search(r"(\d{2}/\d{2}/\d{4})", box)
        if not (link and title and date):
            continue
        clock = parse_clock((re.search(r"Doors:\s*([^<]+)<", box) or [None, ""])[1]) or "20:00"
        img = re.search(r'<img[^>]*src="([^"]+)"', box)
        try:
            day = datetime.strptime(date.group(1), "%m/%d/%Y").strftime("%Y-%m-%d")
        except ValueError:
            continue  # the odd malformed date on their site
        head, support = split_lineup(clean_title(text(title.group(1))))
        out.append(show("palladium", head, f"{day}T{clock}", support, image=img.group(1) if img else None,
                        url=link.group(1), source="palladium"))
    return out


def src_pier17():
    out = []
    for sec in fetch("https://rooftopatpier17.com/").split('<section class="event__single')[1:]:
        if "Concerts" not in sec[:120]:
            continue
        title = re.search(r"<h2>(.*?)</h2>", sec, re.S)
        date = re.search(r'event__date">\s*([A-Z][a-z]{2}, [A-Z][a-z]{2} \d{1,2}, \d{4})', sec)
        if not (title and date):
            continue
        img = re.search(r'<img src="([^"]+)"', sec)
        tickets = re.search(r'<a href="([^"]+)" class="button" target="_blank"', sec)
        info = re.search(r'<a href="(https://rooftopatpier17\.com/events/[^"]+)"', sec)
        day = datetime.strptime(date.group(1), "%a, %b %d, %Y").strftime("%Y-%m-%d")
        head, support = split_lineup(clean_title(text(title.group(1))))
        out.append(show("pier17", head, f"{day}T19:00", support, image=img.group(1) if img else None,
                        url=html.unescape(tickets.group(1)) if tickets else (info.group(1) if info else None), source="pier17"))
    return out


def src_sobs():
    out = []
    for card in fetch("https://sobs.com/").split('<article class="event-card')[1:]:
        link = re.search(r'data-link="([^"]+)"', card)
        title = re.search(r"<h4[^>]*>(.*?)</h4>", card, re.S)
        date = re.search(r"calendar-event-line[^>]*></i>\s*([A-Z][a-z]{2} \d{1,2}, \d{4})", card)
        if not (link and title and date):
            continue
        clock = parse_clock((re.search(r"time-line[^>]*></i>\s*([^<]+)<", card) or [None, ""])[1]) or "20:00"
        img = re.search(r"background-image:url\(([^)]+)\)", card)
        day = datetime.strptime(date.group(1), "%b %d, %Y").strftime("%Y-%m-%d")
        head, support = split_lineup(clean_title(text(title.group(1))))
        out.append(show("sobs", head, f"{day}T{clock}", support, image=img.group(1) if img else None,
                        url=link.group(1), source="sobs"))
    return out


def src_squarespace_events(url, venue):
    """Squarespace event pages publish their calendar as JSON (?format=json)."""
    data = json.loads(fetch(url + ("&" if "?" in url else "?") + "format=json"))
    base = "{0.scheme}://{0.netloc}".format(urlparse(url))
    out = []
    for e in data.get("upcoming") or []:
        start = datetime.fromtimestamp(e["startDate"] / 1000, NYC).strftime("%Y-%m-%dT%H:%M")
        head, support = split_lineup(clean_title(text(e.get("title", ""))), commas=True)
        out.append(show(venue, head, start, support, image=e.get("assetUrl"),
                        url=base + e["fullUrl"] if e.get("fullUrl") else url, source="squarespace"))
    return out


def src_eventbrite_widget(url, venue):
    """Venue sites using the 'Widget for Eventbrite' WordPress plugin (Littlefield)."""
    out = []
    for art in fetch(url).split('<article class="wfea-venue__event')[1:]:
        when = re.search(r'datetime="([^"]+)"', art)
        title = re.search(r'entry-title[^>]*>\s*<a[^>]*title="Eventbrite link to ([^"]+)"', art)
        link = re.search(r'href="(/event/\?wfea_eb_id=\d+)"', art)
        if not (when and title):
            continue
        img = re.search(r'<img[^>]*src="([^"]+)"', art)
        head, support = split_lineup(clean_title(text(title.group(1))), commas=True)
        out.append(show(venue, head, local_iso(when.group(1)), support, image=html.unescape(img.group(1)) if img else None,
                        url="{0.scheme}://{0.netloc}".format(urlparse(url)) + link.group(1) if link else url, source="eventbrite-widget"))
    return out


def src_wp_sobs():
    """SOB's publishes every show (date, time, price) through its WordPress feed."""
    out, page = [], 1
    today = datetime.now(NYC).strftime("%Y%m%d")
    while page <= 6:
        try:
            items = json.loads(fetch(f"https://sobs.com/wp-json/wp/v2/events?per_page=100&page={page}"))
        except urllib.error.HTTPError:
            break
        if not items:
            break
        for e in items:
            a = e.get("acf") or {}
            day = a.get("event_date") or ""
            if len(day) != 8 or day < today:
                continue
            clock = (a.get("event_time") or "20:00")[:5]
            title = text(a.get("event_title") or e["title"]["rendered"])
            price = re.search(r"\$\s?(\d+)", a.get("event_price") or "")
            img = a.get("event_image") if isinstance(a.get("event_image"), str) else None
            head, support = split_lineup(clean_title(title))
            out.append(show("sobs", head, f"{day[:4]}-{day[4:6]}-{day[6:]}T{clock}", support,
                            tagline=text(a.get("event_subt") or ""), price=int(price.group(1)) if price else None,
                            image=img, url=e.get("link"), source="sobs"))
        page += 1
    return out


# LPR's feed tags each show with the room it's in. Only these are ours; the rest (LA, SF, Miami...) are skipped.
LPR_SPACES = {
    "main-space": "lpr", "littlefield": "littlefield", "the-town-hall": "townhall", "national-sawdust": "sawdust",
    "xanadu": "xanadu", "the-sultan-room": "sultan", "knockdown-center": "knockdown", "pioneer-works": "pioneerworks",
    "public-records": "publicrecords", "adler-hall-at-new-york-society-for-ethical-culture": "ethical",
}


def src_wp_lpr():
    """LPR's WordPress feed: newest posts first; the date/time sit in each post's description."""
    out = []
    today = datetime.now(NYC).date()
    for page in range(1, 5):
        items = json.loads(fetch(f"https://lpr.com/wp-json/wp/v2/lpr_events?per_page=100&page={page}"
                                 "&_fields=title,link,class_list,yoast_head_json"))
        future = 0
        for e in items:
            desc = (e.get("yoast_head_json") or {}).get("og_description") or ""
            m = re.search(r"on [A-Z][a-z]+, ([A-Z][a-z]+ \d{1,2})(?:st|nd|rd|th)?, (\d{4})(?:\s*\|\s*([^|]+))?", desc)
            if not m:
                continue
            day = datetime.strptime(f"{m.group(1)} {m.group(2)}", "%B %d %Y").date()
            if day < today:
                continue
            future += 1
            spaces = [c[len("event_spaces-"):] for c in e.get("class_list", []) if c.startswith("event_spaces-")]
            venue = LPR_SPACES.get(spaces[0]) if len(spaces) == 1 else None
            if not venue:
                VENUE_MISMATCHES.append(f"{text(e['title']['rendered'])} — LPR feed, room {spaces}; skipped")
                continue
            times = m.group(3) or ""
            clock = parse_clock(times.split("|")[-1] if "show" in times.lower() else times) or "19:00"
            show_m = re.search(r"(\d{1,2}(?::\d\d)?\s*[AP]M)\s*show", desc, re.I)
            clock = parse_clock(show_m.group(1)) if show_m else clock
            tags = [c[4:].replace("-", " ") for c in e.get("class_list", []) if c.startswith("tag-")]
            head, support = split_lineup(clean_title(text(e["title"]["rendered"])), commas=True)
            price = None
            try:  # base ticket price is printed on the show page ("Event Ticket: $25")
                pm = re.search(r"Event Ticket:\s*\$\s?(\d+)", text(fetch(e["link"])))
                price = int(pm.group(1)) if pm else None
            except Exception:
                pass
            out.append(show(venue, head, f"{day:%Y-%m-%d}T{clock}", support, price=price, url=e["link"],
                            genres=tags, source="lpr"))
        if future == 0 and page > 1:
            break  # older posts from here on
    return out


def src_public_records():
    """Public Records' own calendar lists every show (DICE's venue page stops at 30)."""
    now = datetime.now(NYC)
    out = []
    for m in re.finditer(r'<a target="_blank" class="event table-row" href="([^"]+)"[^>]*>(.*?)</a>', fetch("https://publicrecords.nyc/"), re.S):
        link, body = m.group(1), m.group(2)
        date = re.search(r'class="table-cell date">\s*[A-Z][a-z]{2} (\d{1,2})\.(\d{1,2})<br\s*/?>\s*([A-Za-z]+), ([^,<]+)', body)
        title = re.search(r'class="table-cell title">\s*(.*?)<span', body, re.S)
        if not (date and title) or date.group(3).lower() == "etc":  # "Etc" = talks, listening nights, etc.
            continue
        day = datetime(now.year, int(date.group(1)), int(date.group(2)))
        if day.date() < (now - timedelta(days=30)).date():
            day = day.replace(year=now.year + 1)
        head, support = split_lineup(clean_title(text(title.group(1))), commas=True)
        out.append(show("publicrecords", head, f"{day:%Y-%m-%d}T{parse_clock(date.group(4)) or '20:00'}", support,
                        url=link, genres=["Dance"] if date.group(3).lower() == "club" else [], source="publicrecords"))
    return out


def src_dice_widget(url, venues):
    """Venue sites that embed DICE's event widget (Union Pool, The Sultan Room) show every show,
    while DICE's own venue pages stop at 30. The widget only appears in a real browser, so this opens
    the page with Playwright (installed in the GitHub Action). venues: text on the card -> venue id."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError("Playwright not installed here (runs in GitHub Actions) — DICE backup used")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(user_agent=UA)
        page.goto(url, wait_until="networkidle", timeout=90000)
        page.wait_for_selector(".dice_events article", timeout=45000)
        for _ in range(8):  # "load more" if the widget has it
            more = page.query_selector("button:has-text('Load more'), button:has-text('Show more')")
            if not more:
                break
            more.click()
            page.wait_for_timeout(1500)
        cards = page.eval_on_selector_all(".dice_events article", """els => els.map(e => ({
            text: e.innerText, href: (e.querySelector('a[href*="dice"]') || {}).href || null,
            img: (e.querySelector('img') || {}).src || null }))""")
        browser.close()
    now = datetime.now(NYC)
    out = []
    for c in cards:
        lines = [l.strip() for l in c["text"].split("\n") if l.strip()]
        when = next((re.search(r"([A-Z][a-z]{2}) (\d{1,2}) ([A-Z][a-z]{2})\s*[―-]\s*(\d{1,2}(?::\d\d)?\s*[ap]m)", l) for l in lines
                     if re.search(r"\d{1,2} [A-Z][a-z]{2}\s*[―-]", l)), None)
        if not lines or not when:
            continue
        if any(re.fullmatch(r"cancell?ed|postponed", l, re.I) for l in lines):
            continue
        where = lines[1] if len(lines) > 1 else ""
        if re.search(r"\d{1,2} [A-Z][a-z]{2}\s*[―-]", where):
            where = ""  # single-venue calendars (Union Pool) don't print a venue on each card
        # the printed venue decides; a show promoted at another of our venues goes there (exact names only)
        venue = venues.get(_norm_venue(where)) or (_our_venue(where) if where else None)
        if not venue:
            VENUE_MISMATCHES.append(f"{lines[0]} — {url} calendar, but at {where!r}; skipped")
            continue
        day = datetime.strptime(f"{when.group(2)} {when.group(3)} {now.year}", "%d %b %Y")
        if day.date() < (now - timedelta(days=30)).date():
            day = day.replace(year=now.year + 1)
        head, support = split_lineup(clean_title(lines[0]), commas=True)
        out.append(show(venue, head, f"{day:%Y-%m-%d}T{parse_clock(when.group(4)) or '20:00'}", support,
                        image=c.get("img"), url=c.get("href"), source="dice-widget"))
    return out


# Arena/theater calendars mix in sports, comedy and family shows — keep music only.
NOT_CONCERT = re.compile(
    r"\bvs\.?\b|\bv\.\s|liberty|nets\b|knicks|rangers|islanders|basketball|hockey|boxing|\bufc\b|\bwwe\b|\baew\b|"
    r"wrestling|playoffs?|preseason|globetrotters|monster jam|disney|on ice|paw patrol|sesame|bluey|cocomelon|"
    r"circus|graduation|commencement|comedy|comedian|stand-?up|podcast|live taping|in conversation|an evening with .* author|"
    r"magic show|illusionist|film|screening|ballet|nutcracker|dance company|gala|awards",
    re.I,
)


def src_barclays():
    out = []
    for block in fetch("https://www.barclayscenter.com/events").split('data-timestamp="')[1:]:
        ts = int(block.split('"', 1)[0])
        title = re.search(r"<h3>(.*?)</h3>", block, re.S)
        if not title:
            continue
        name = text(title.group(1))
        tagline = text((re.search(r"<h4>(.*?)</h4>", block, re.S) or [None, ""])[1])
        if NOT_CONCERT.search(f"{name} {tagline}"):
            continue
        img = re.search(r'<img src="([^"]+)"', block)
        tickets = re.search(r'href="(https?://[^"]*ticketmaster[^"]*)"', block)
        start = datetime.fromtimestamp(ts, NYC).strftime("%Y-%m-%dT%H:%M")
        out.append(show("barclays", name, start, tagline="" if tagline.lower() == name.lower() else tagline,
                        image=img.group(1) if img else None, url=html.unescape(tickets.group(1)) if tickets else None,
                        source="barclays"))
    return out


def src_sony_hall():
    out = []
    for block in fetch("https://sonyhall.com/shows/").split("<li class='show-group")[1:]:
        name = re.search(r"<h2\s*><a href='([^']+)'>(.*?)</a>", block, re.S)
        date = re.search(r"<time datetime='(\d{4}-\d{2}-\d{2})'", block)
        if not (name and date):
            continue
        prefix = text((re.search(r"class='prefix-text'>(.*?)</div>", block, re.S) or [None, ""])[1])
        sub = text((re.search(r"<h3>(.*?)</h3>", block, re.S) or [None, ""])[1])
        tod = text((re.search(r"class='tod'>(.*?)</div>", block, re.S) or [None, ""])[1])
        clock = parse_clock(tod.split("SHOW")[-1]) or parse_clock(tod) or "20:00"
        img = re.search(r"data-src='([^']+)'", block)
        tickets = re.search(r"href='(https?://[^']*(?:ticketmaster|ticketweb)[^']*)'", block)
        head, support = split_lineup(clean_title(text(name.group(2))))
        out.append(show("sonyhall", head, f"{date.group(1)}T{clock}", support, tagline=sub or prefix,
                        image=img.group(1) if img else None, url=html.unescape(tickets.group(1)) if tickets else name.group(1),
                        source="sonyhall"))
    return out


def src_kings_theatre():
    """ATG's Kings Theatre page tags each event (Concert / Comedy / Family / Talk…) — keep concerts."""
    page = ""
    for n in range(1, 6):  # ATG paginates the list
        try:
            chunk = fetch("https://us.atgtickets.com/venues/kings-theatre-brooklyn/whats-on/" + (f"?page={n}" if n > 1 else ""))
        except urllib.error.HTTPError:
            break
        if n > 1 and "MuiCardContent-root" not in chunk:
            break
        page += chunk
    out = []
    for m in re.finditer(r'<div class="MuiCardContent-root[^"]*">(.*?)(?=<div class="MuiCardContent-root|\Z)', page, re.S):
        card = m.group(1)[:4000]
        name = re.search(r'<h2 class="MuiBox-root[^"]*">(.*?)</h2>', card, re.S)
        kind = re.search(r'bodySmall[^"]*">(Concert|Comedy|Dance|Family|Events|Talk|Film|Theatre|Musical)</p>', card)
        date = re.search(r'bodySmall[^"]*">([A-Z][a-z]{2}, [A-Z][a-z]{2} \d{1,2}, \d{4})</p>', card)
        if not (name and date) or not kind or kind.group(1) != "Concert":
            continue
        link = re.search(r'href="(/events/[^"]+?/kings-theatre-brooklyn/)"', card)
        imgs = re.findall(r'<img class="MuiCardMedia-root[^>]*?src="([^"]+)"', page[:m.start()])
        day = datetime.strptime(date.group(1), "%a, %b %d, %Y").strftime("%Y-%m-%d")
        head, support = split_lineup(clean_title(text(name.group(1))))
        out.append(show("kings", head, f"{day}T20:00", support, image=imgs[-1] if imgs else None,
                        url="https://us.atgtickets.com" + link.group(1) if link else None, source="kings"))
    return out


SKIP_TM = re.compile(r"parking|suite|premium seat|vip package|upgrade|tour package|hospitality|gift card", re.I)


MUSIC_SEGMENT = "KZFzniwnSyZfZ7v7nJ"


def _event_key(url):
    """Ticketmaster event id at the end of a ticket link (.../event/300064EC4E15E471)."""
    m = re.search(r"/event/([0-9A-Za-z]{10,})", url or "")
    return m.group(1) if m else None


def _tm_not_music(key, tm_id):
    """Remember this venue's non-music Ticketmaster events (comedy, talks, theater), so a venue site that
    lists everything (The Bell House, Gramercy, Irving Plaza...) can't slip them back in."""
    page = 0
    while page < 5:
        q = urllib.parse.urlencode({"apikey": key, "venueId": tm_id, "classificationId": f"-{MUSIC_SEGMENT}",
                                    "size": 200, "page": page, "countryCode": "US"})
        data = json.loads(fetch("https://app.ticketmaster.com/discovery/v2/events.json?" + q, api=True))
        time.sleep(0.25)
        for e in (data.get("_embedded") or {}).get("events", []):
            TM_NOT_MUSIC.update(k for k in (e.get("id"), _event_key(e.get("url"))) if k)
        info = data.get("page", {})
        if info.get("number", 0) + 1 >= info.get("totalPages", 1):
            break
        page += 1


def src_ticketmaster():
    """Ticketmaster Discovery API (official) — music events only, so no Knicks/Nets/Rangers games."""
    key = os.environ.get("TICKETMASTER_API_KEY") or _env_value("TICKETMASTER_API_KEY")
    if not key:
        raise RuntimeError("no TICKETMASTER_API_KEY yet — skipped")
    out = []
    for tm_id, venue in TICKETMASTER_VENUES.items():
        _tm_not_music(key, tm_id)
        events, page = [], 0
        while True:
            q = urllib.parse.urlencode({"apikey": key, "venueId": tm_id, "classificationName": "music",
                                        "size": 200, "page": page, "sort": "date,asc", "countryCode": "US"})
            data = json.loads(fetch("https://app.ticketmaster.com/discovery/v2/events.json?" + q, api=True))
            events += (data.get("_embedded") or {}).get("events", [])
            time.sleep(0.25)  # stay under 5 requests/second
            info = data.get("page", {})
            if info.get("number", 0) + 1 >= info.get("totalPages", 1):
                break
            page += 1
        for e in events:
            if not e.get("name"):
                continue  # Ticketmaster occasionally sends an event with no name
            start = e.get("dates", {}).get("start", {})
            if re.search(r"ticketmaster\.com/event/Z", e.get("url", "")):
                continue  # resale-only listing, not the official sale
            if not start.get("localDate") or SKIP_TM.search(e["name"]) or e.get("dates", {}).get("status", {}).get("code") == "cancelled":
                continue
            acts = [a["name"] for a in (e.get("_embedded") or {}).get("attractions", []) if a.get("name")]
            if not acts:  # small clubs often put the whole lineup in the title: "A, B, C"
                h, sup = split_lineup(clean_title(e["name"]), commas=VENUE_SIZE.get(venue) != "large")
                acts = [h] + sup
            head = acts[0]
            imgs = sorted((i for i in e.get("images", []) if i.get("ratio") == "16_9"), key=lambda i: -i.get("width", 0))
            img = next((i["url"] for i in reversed(imgs) if i.get("width", 0) >= 640), imgs[0]["url"] if imgs else None)
            genres = [c.get(k, {}).get("name", "") for c in e.get("classifications", []) for k in ("genre", "subGenre")]
            price = min((p.get("min") for p in e.get("priceRanges", []) if p.get("min")), default=None)
            out.append(show(venue, head, f"{start['localDate']}T{(start.get('localTime') or '19:30')[:5]}", acts[1:],
                            tagline=e["name"] if e["name"] != head else "", price=round(price) if price else None,
                            image=img, url=e.get("url"),
                            genres=[g for g in genres if g and g.lower() not in ("undefined", "other")], source="ticketmaster"))
    return out


def _norm_venue(name):
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


EXACT_VENUE_NAMES = {_norm_venue(v["name"]): v["id"] for v in VENUES}
EXACT_VENUE_NAMES.update({_norm_venue(k): v for k, v in {**BOWERY_NAMES, **VENUE_NAMES}.items()})
VENUE_BY_ID = {v["id"]: v for v in VENUES}
VENUE_MISMATCHES = []  # listings a venue's own feed had that are actually somewhere else
TM_NOT_MUSIC = set()  # Ticketmaster event ids at our venues that Ticketmaster doesn't classify as music
NEAR_MISSES = {}  # unmatched venue names that look like one of ours; reported so they can be added by hand


def _km(lat1, lng1, lat2, lng2):
    return math.hypot((lat1 - lat2) * 111.0, (lng1 - lng2) * 84.0)


def _our_venue(name, lat=None, lng=None):
    """A citywide listing's venue name -> our venue id, by EXACT name only (see VENUE_NAMES in venues.py).
    A match more than 3 km from our venue is rejected too (same name, different place)."""
    n = _norm_venue(name)
    vid = EXACT_VENUE_NAMES.get(n)
    ours = VENUE_BY_ID.get(vid)
    if vid and lat and lng and ours and ours.get("lat") and _km(float(lat), float(lng), ours["lat"], ours["lng"]) > 3:
        NEAR_MISSES.setdefault(name, f"named like {ours['name']} but {_km(float(lat), float(lng), ours['lat'], ours['lng']):.1f} km away — rejected")
        return None
    if vid:
        return vid
    # Not matched. If it resembles one of ours (shares its name, or sits within 150 m), flag it for review.
    for v in VENUES:
        k = _norm_venue(v["name"])
        close = lat and lng and v.get("lat") and _km(float(lat), float(lng), v["lat"], v["lng"]) < 0.15
        if n and ((len(k) >= 5 and k in n) or (len(n) >= 5 and n in k) or close):
            NEAR_MISSES.setdefault(name, f"looks like {v['name']} but isn't an exact known name — not matched")
            break
    return None


def src_seatgeek():
    """SeatGeek Platform API (official, free key): every NYC concert in one sweep, matched to our venues.
    Runs last, so it only fills dates nothing else had. Links go to the venue's own site, never resale."""
    key = os.environ.get("SEATGEEK_CLIENT_ID") or _env_value("SEATGEEK_CLIENT_ID")
    if not key:
        raise RuntimeError("no SEATGEEK_CLIENT_ID — skipped")
    fallback = set(SEATGEEK_VENUES.values())
    out, page = [], 1
    while page <= 40:
        q = urllib.parse.urlencode({"client_id": key, "lat": 40.73, "lon": -73.94, "range": "13mi",
                                    "taxonomies.name": "concert", "per_page": 100, "page": page})
        data = json.loads(fetch("https://api.seatgeek.com/2/events?" + q, api=True))
        for e in data.get("events", []):
            v = e.get("venue") or {}
            venue = SEATGEEK_VENUES.get(v.get("id")) or _our_venue(v.get("name"), (v.get("location") or {}).get("lat"),
                                                                    (v.get("location") or {}).get("lon"))
            if not venue:
                _note_candidate(v.get("name"), "seatgeek", (v.get("location") or {}).get("lat"), (v.get("location") or {}).get("lon"))
                continue
            link = VENUE_SITES.get(venue) or (e.get("url") if venue in fallback else None)
            if not link or (e.get("time_tbd") and e.get("date_tbd")):
                continue
            performers = sorted(e.get("performers", []), key=lambda p: not p.get("primary"))
            acts = [p["name"] for p in performers] or [e.get("short_title") or e["title"]]
            genres = [g["name"] for p in performers[:1] for g in (p.get("genres") or [])]
            out.append(show(venue, acts[0], e["datetime_local"][:16], acts[1:],
                            tagline=e["title"] if e["title"] not in (acts[0], e.get("short_title")) else "",
                            url=link, genres=genres, source="seatgeek"))
        meta = data.get("meta", {})
        if not data.get("events") or page * meta.get("per_page", 100) >= meta.get("total", 0):
            break
        page += 1
    return out


def src_eventbrite(path, venue, only_venue_name=None):
    """Eventbrite API (official, private token) — a venue's or organizer's live events."""
    token = os.environ.get("EVENTBRITE_TOKEN") or _env_value("EVENTBRITE_TOKEN")
    if not token:
        raise RuntimeError("no EVENTBRITE_TOKEN — skipped")
    events, cont = [], None
    while True:
        q = {"status": "live", "order_by": "start_asc", "expand": "venue,ticket_availability"}
        if cont:
            q["continuation"] = cont
        req = urllib.request.Request(f"https://www.eventbriteapi.com/v3/{path}?" + urllib.parse.urlencode(q),
                                     headers={"Authorization": f"Bearer {token}", "User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
        events += data.get("events", [])
        if not data.get("pagination", {}).get("has_more_items"):
            break
        cont = data["pagination"]["continuation"]
        time.sleep(0.3)
    out = []
    for e in events:
        if e.get("category_id") not in (None, "103"):  # 103 = Music; skips comedy, talks, classes
            continue
        vname = (e.get("venue") or {}).get("name") or ""
        if only_venue_name and only_venue_name.lower() not in vname.lower():
            continue  # e.g. Elsewhere also sells shows it promotes at other venues
        price = ((e.get("ticket_availability") or {}).get("minimum_ticket_price") or {}).get("major_value")
        head, support = split_lineup(clean_title(e["name"]["text"]), commas=True)
        out.append(show(venue, head, e["start"]["local"][:16], support, price=price_num(price),
                        image=(e.get("logo") or {}).get("url"), url=e.get("url"), source="eventbrite"))
    return out


def src_ticketmaster_mirror():
    """Every NYC music event Ticketmaster knows about, including shows it only lists for resale
    (their official sale is on a system we can't read, like See Tickets). Used last, just to fill
    shows the other sources missed, and always linked to the venue's own site — never resale."""
    key = os.environ.get("TICKETMASTER_API_KEY") or _env_value("TICKETMASTER_API_KEY")
    if not key:
        raise RuntimeError("no TICKETMASTER_API_KEY — skipped")
    out, now = [], datetime.now(NYC).date()
    for w in range(0, DAYS_AHEAD, 7):  # weekly windows: the API stops at 1,000 results per query
        a, b = now + timedelta(days=w), now + timedelta(days=w + 7)
        page = 0
        while True:
            q = urllib.parse.urlencode({"apikey": key, "classificationName": "music", "latlong": "40.73,-73.94",
                                        "radius": 13, "unit": "miles", "size": 200, "page": page,
                                        "startDateTime": f"{a}T00:00:00Z", "endDateTime": f"{b}T00:00:00Z"})
            data = json.loads(fetch("https://app.ticketmaster.com/discovery/v2/events.json?" + q, api=True))
            time.sleep(0.25)
            for e in (data.get("_embedded") or {}).get("events", []):
                if not e.get("name"):
                    continue
                v = ((e.get("_embedded") or {}).get("venues") or [{}])[0]
                loc = v.get("location") or {}
                venue = TICKETMASTER_VENUES.get(v.get("id")) or _our_venue(
                    v.get("name"), float(loc["latitude"]) if loc.get("latitude") else None,
                    float(loc["longitude"]) if loc.get("longitude") else None)
                start = e.get("dates", {}).get("start", {})
                if not venue:
                    _note_candidate(v.get("name"), "ticketmaster", float(loc["latitude"]) if loc.get("latitude") else None,
                                    float(loc["longitude"]) if loc.get("longitude") else None)
                    continue
                if not start.get("localDate") or e.get("dates", {}).get("status", {}).get("code") == "cancelled":
                    continue
                if SKIP_TM.search(e["name"]):
                    continue
                acts = [x["name"] for x in (e.get("_embedded") or {}).get("attractions", []) if x.get("name")]
                if not acts:
                    h, sup = split_lineup(clean_title(e["name"]), commas=VENUE_SIZE.get(venue) != "large")
                    acts = [h] + sup
                official = not re.search(r"ticketmaster\.com/event/Z", e.get("url", ""))
                imgs = sorted((i for i in e.get("images", []) if i.get("ratio") == "16_9"), key=lambda i: -i.get("width", 0))
                img = next((i["url"] for i in reversed(imgs) if i.get("width", 0) >= 640), imgs[0]["url"] if imgs else None)
                genres = [c.get(k, {}).get("name", "") for c in e.get("classifications", []) for k in ("genre", "subGenre")]
                out.append(show(venue, acts[0], f"{start['localDate']}T{(start.get('localTime') or '20:00')[:5]}", acts[1:],
                                image=img, url=e.get("url") if official else VENUE_SITES.get(venue),
                                genres=[g for g in genres if g and g.lower() not in ("undefined", "other")],
                                source="ticketmaster-mirror"))
            info = data.get("page", {})
            if info.get("number", 0) + 1 >= info.get("totalPages", 1) or page >= 4:
                break
            page += 1
    return out


AI_REPORT = []
CANDIDATES = {}  # music venues seen in citywide sweeps that aren't on Shindig yet: name -> info


def _note_candidate(name, source, lat=None, lng=None):
    if not name:
        return
    c = CANDIDATES.setdefault(re.sub(r"[^a-z0-9]", "", name.lower())[:30],
                              {"name": name, "events": 0, "sources": set(), "lat": lat, "lng": lng})
    c["events"] += 1
    c["sources"].add(source)


def src_ai():
    """Browser + Claude for venue calendars no platform reader understands (see ai_reader.py)."""
    events, report = ai_reader.read_venues({v["id"]: v for v in VENUES}, UA)
    AI_REPORT.extend(report)
    out = []
    for e in events:
        if not e.get("date"):
            continue
        clock = e.get("time") or "20:00"
        out.append(show(e["venue"], e["headliner"], f"{e['date']}T{clock[:5]}", e.get("support") or [],
                        price=price_num(e.get("base_price")) if e.get("base_price") else None,
                        url=e.get("ticket_url") or VENUE_SITES.get(e["venue"]), source="ai-reader"))
    return out


def _env_value(name):
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith(name + "="):
                return line.split("=", 1)[1].strip()
    return None


SOURCES = [
    ("Ticketmaster API (official listings for Ticketmaster/TicketWeb venues)", src_ticketmaster),
    ("Eventbrite API: Elsewhere", lambda: src_eventbrite("organizers/105655500371/events/", "elsewhere", only_venue_name="Elsewhere")),
    ("Eventbrite API: Littlefield", lambda: src_eventbrite("venues/35241107/events/", "littlefield")),
    ("Irving Plaza", lambda: src_jsonld("https://www.irvingplaza.com/", "irving")),
    ("Brooklyn Paramount", lambda: src_jsonld("https://www.brooklynparamount.com/", "paramount")),
    ("Warsaw", lambda: src_jsonld("https://www.warsawconcerts.com/", "warsaw")),
    ("Gramercy Theatre", lambda: src_jsonld("https://www.thegramercytheatre.com/", "gramercy")),
    ("Full calendar: Union Pool", lambda: src_dice_widget("https://www.union-pool.com/calendar", {"unionpool": "unionpool", "": "unionpool"})),
    ("Full calendar: The Sultan Room", lambda: src_dice_widget("https://thesultanroom.com/",
        {"thesultanroom": "sultan", "thesultanroomrooftop": "sultanroof", "sultanroomrooftop": "sultanroof"})),
    ("Full calendar: Saint Vitus", lambda: src_dice_widget("https://www.saintvitusbar.com/", {"saintvitus": "saintvitus", "saintvitusbar": "saintvitus"})),
    ("Union Pool (DICE)", lambda: src_jsonld("https://dice.fm/venue/union-pool-nbvl", "unionpool")),
    ("The Sultan Room (DICE)", lambda: src_jsonld("https://dice.fm/venue/the-sultan-room-e27w", "sultan")),
    ("Sultan Room Rooftop (DICE)", lambda: src_jsonld("https://dice.fm/venue/the-sultan-room-rooftop-x57a", "sultanroof")),
    ("Bowery Presents NYC", src_bowery_presents),
    ("Forest Hills Stadium", lambda: src_bowery_presents(58, {"Forest Hills Stadium": "foresthills"})),
    ("Bowery Ballroom", lambda: src_mercury_east("https://mercuryeastpresents.com/boweryballroom/", "bowery")),
    ("Mercury Lounge", lambda: src_mercury_east("https://mercuryeastpresents.com/mercurylounge/", "mercury")),
    ("LPR", src_wp_lpr),
    ("Elsewhere", src_elsewhere),
    ("Brooklyn Bowl", src_brooklyn_bowl),
    ("Public Records", src_public_records),
    ("Saint Vitus (DICE)", lambda: src_jsonld("https://dice.fm/venue/saint-vitus-rgrv", "saintvitus")),
    ("Knockdown Center (DICE)", lambda: src_jsonld("https://dice.fm/venue/knockdown-center-e776", "knockdown")),
    ("Knockdown Center Ruins (DICE)", lambda: src_jsonld("https://dice.fm/venue/ruins-at-knockdown-center-owog", "knockdown")),
    ("Xanadu (DICE)", lambda: src_jsonld("https://dice.fm/venue/xanadu-5knl", "xanadu")),
    ("SILO (DICE)", lambda: src_jsonld("https://dice.fm/venue/silo-brooklyn-eb72", "silo")),
    ("Market Hotel", lambda: src_venuepilot(100, "markethotel")),
    ("TV Eye", lambda: src_seetickets_wp("https://tveyenyc.com/", "tveye")),
    ("H0L0", src_holo),
    ("National Sawdust", src_national_sawdust),
    ("Barclays Center", src_barclays),
    ("Sony Hall", src_sony_hall),
    ("Kings Theatre", src_kings_theatre),
    ("Blue Note", src_blue_note),
    ("Palladium Times Square", src_palladium),
    ("The Rooftop at Pier 17", src_pier17),
    ("SOB's", src_wp_sobs),
    ("Melrose Ballroom", lambda: src_squarespace_events("https://www.melroseballroom.com/events", "melrose")),
    ("Littlefield", lambda: src_eventbrite_widget("https://littlefieldnyc.com/all-shows/", "littlefield")),
    ("The Bell House", lambda: src_jsonld("https://www.thebellhouseny.com/", "bellhouse")),
    ("AI reader (venue pages no other reader understands)", src_ai),
    ("SeatGeek API (fills any shows the sources above missed)", src_seatgeek),
    ("Ticketmaster citywide (fills the rest; resale-only listings link to the venue)", src_ticketmaster_mirror),
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


# How much to trust each venue's count, based on where its shows came from.
COMPLETE_SOURCES = {"ticketmaster", "eventbrite", "bowery", "dice-widget", "lpr", "sobs", "publicrecords", "brooklynbowl",
                    "venuepilot", "seetickets-wp", "holo", "nationalsawdust", "barclays", "sonyhall", "kings", "bluenote",
                    "palladium", "pier17", "squarespace", "eventbrite-widget", "mercuryeast", "elsewhere", "jsonld"}
FILL_SOURCES = {"seatgeek", "ticketmaster-mirror"}


NOT_VENUES = re.compile(r"new jersey|nj\b|newark|jersey city|hoboken|long island|belmont|elmont|ubs arena|prudential|"
                        r"metlife|rutherford|englewood|bergen|american dream|stadium tour|online|virtual|tba|tbd", re.I)


def track_venue_health(shows):
    """Openings and closings — flags for a person to review; nothing is removed automatically.
    data/venue_health.json remembers, per venue, the last run that found
    upcoming shows and whether its website loaded; data/venue_candidates.json lists venues that keep
    appearing in citywide listings but aren't on Shindig yet."""
    path = ROOT / "data" / "venue_health.json"
    health = json.loads(path.read_text()) if path.exists() else {}
    today = datetime.now(NYC).strftime("%Y-%m-%d")
    counts = {}
    for s in shows:
        counts[s["venue"]] = counts.get(s["venue"], 0) + 1
    notes = []
    for v in VENUES:
        h = health.setdefault(v["id"], {"first_checked": today, "site_failures": 0})
        if counts.get(v["id"]):
            h["last_shows_seen"] = today
        site = VENUE_SITES.get(v["id"])
        if site:
            try:
                req = urllib.request.Request(site, headers={"User-Agent": UA})
                urllib.request.urlopen(req, timeout=20).close()
                h["site_failures"] = 0
            except urllib.error.HTTPError as e:
                h["site_failures"] = 0 if e.code in (401, 403, 405, 429) else h.get("site_failures", 0) + 1  # blocked ≠ gone
            except Exception:
                h["site_failures"] = h.get("site_failures", 0) + 1
        last = h.get("last_shows_seen") or h["first_checked"]
        quiet_days = (datetime.fromisoformat(today) - datetime.fromisoformat(last)).days
        # Only ever a prompt to check, never an automatic removal. Seasonal (outdoor) venues are skipped.
        if quiet_days >= 14 and v["id"] not in SEASONAL_VENUES:
            notes.append(f"    {v['name']}: no upcoming shows from any source for {quiet_days} days — worth checking")
        if h.get("site_failures", 0) >= 3:
            notes.append(f"    {v['name']}: website hasn't loaded for {h['site_failures']} runs — check if it's still open")
    path.write_text(json.dumps(health, indent=1, sort_keys=True))

    cands = [dict(c, sources=sorted(c["sources"])) for k, c in CANDIDATES.items()
             if c["events"] >= 3 and not NOT_VENUES.search(c["name"])
             and not any(k.startswith(x) for x in IGNORED_CANDIDATES)]
    cands.sort(key=lambda c: -c["events"])
    (ROOT / "data" / "venue_candidates.json").write_text(json.dumps(cands, indent=1, ensure_ascii=False))
    (ROOT / "data" / "venue_match_review.json").write_text(json.dumps(
        {"near_misses": NEAR_MISSES, "skipped_other_venue": sorted(set(VENUE_MISMATCHES))}, indent=1, ensure_ascii=False))
    if VENUE_MISMATCHES:
        print(f"\n  skipped {len(set(VENUE_MISMATCHES))} listings that a feed had under the wrong venue (data/venue_match_review.json)")
    if NEAR_MISSES:
        print("\n  venue names NOT matched that look like ours (add to VENUE_NAMES only if it's truly the same room):")
        for name, why in sorted(NEAR_MISSES.items()):
            print(f"    {name!r}: {why}")
    print("\n  venue health (possible closings):" if notes else "\n  venue health: no closing signals")
    for n in notes:
        print(n)
    if cands:
        print(f"  possible new venues (not on Shindig, 3+ music events in citywide listings): {len(cands)}")
        for c in cands[:15]:
            print(f"    {c['name'][:36]:36} {c['events']:3} events  ({', '.join(c['sources'])})")


def write_coverage(shows):
    """data/coverage.json + a printed list of venues whose counts are probably incomplete."""
    by_venue = {}
    for s in shows:
        by_venue.setdefault(s["venue"], {}).setdefault(s["source"], 0)
        by_venue[s["venue"]][s["source"]] += 1
    rows = []
    for v in VENUES:
        src = by_venue.get(v["id"], {})
        total = sum(src.values())
        main = sum(n for k, n in src.items() if k in COMPLETE_SOURCES)
        dice_capped = v["id"] in {"knockdown", "xanadu", "silo"} or (v["id"] == "saintvitus" and not src.get("dice-widget"))
        if total == 0:
            level = "none: no shows found"
        elif dice_capped and src.get("jsonld", 0) >= 25:
            level = "capped: DICE venue page stops at 30 shows"
        elif main / total >= 0.6:
            level = "good: from an official feed or the venue's full calendar"
        elif src.get("ai-reader", 0) / total >= 0.5:
            level = "ai: read from the venue's page by the AI reader"
        elif sum(src.get(k, 0) for k in FILL_SOURCES) / total >= 0.5:
            level = "fill-in only: SeatGeek/Ticketmaster mirrors, likely incomplete"
        else:
            level = "mixed"
        rows.append({"venue": v["id"], "name": v["name"], "shows": total, "sources": src, "confidence": level})
    (ROOT / "data" / "coverage.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    weak = [r for r in rows if not r["confidence"].startswith("good")]
    print(f"\n  coverage: {len(rows) - len(weak)}/{len(rows)} venues good; check these:")
    for r in sorted(weak, key=lambda r: r["confidence"]):
        print(f"    {r['name'][:28]:28} {r['shows']:3}  {r['confidence']}")


def _act_key(name):
    return re.sub(r"[^a-z0-9]", "", clean_title(name).lower().replace("the ", ""))[:24] or "?"


def show_id(s):
    slug = re.sub(r"[^a-z0-9]+", "-", s["artist"].lower()).strip("-")[:40]
    return f"{s['start'][:10]}-{s['venue']}-{slug}"


def load_existing():
    if not OUT.exists():
        return []
    raw = OUT.read_text()
    return json.loads(raw[raw.index("{"):raw.rindex("}") + 1]).get("shows", [])


def outdoor_season():
    """Rooftop / Outdoor filter goes away when the next week is all cold (highs below 40°F). Open-Meteo: free, no key."""
    try:
        q = urllib.parse.urlencode({"latitude": 40.73, "longitude": -73.94, "daily": "temperature_2m_max",
                                    "temperature_unit": "fahrenheit", "timezone": "America/New_York", "forecast_days": 7})
        highs = json.loads(fetch("https://api.open-meteo.com/v1/forecast?" + q, api=True))["daily"]["temperature_2m_max"]
        print(f"  next 7 days' highs (°F): {highs}")
        return any(h is not None and h >= 40 for h in highs)
    except Exception as e:
        print(f"  weather check failed ({e}); keeping Rooftop / Outdoor on")
        return True


def drop_cross_venue_duplicates(fresh):
    """The same act can't play two of our venues within 3 hours of each other. When two sources disagree
    (a moved show, a presenter's feed listing an off-site show), keep the higher-priority source's venue."""
    by_act = {}
    for s in fresh.values():
        by_act.setdefault((_act_key(s["artist"]), s["start"][:10]), []).append(s)
    for (act, day), group in by_act.items():
        venues = {s["venue"] for s in group}
        if len(venues) < 2 or act == "?":
            continue
        group.sort(key=lambda s: s["_prio"])
        keep = group[0]
        for s in group[1:]:
            gap = abs((datetime.fromisoformat(s["start"]) - datetime.fromisoformat(keep["start"])).total_seconds()) / 3600
            if s["venue"] != keep["venue"] and gap < 3:
                fresh.pop(s["id"], None)
                VENUE_MISMATCHES.append(f"{s['artist']} {day}: listed at {s['venue']} ({s['source']}) and {keep['venue']} "
                                        f"({keep['source']}); kept {keep['venue']}")
    return fresh


def main():
    now = datetime.now(NYC)
    today = now.strftime("%Y-%m-%d")
    horizon = (now + timedelta(days=DAYS_AHEAD)).strftime("%Y-%m-%d")
    oldest = (now - timedelta(days=KEEP_PAST_DAYS)).strftime("%Y-%m-%d")

    fresh, report, big_slots = {}, [], set()
    # Sources run in priority order (official feeds first). A later source only fills in
    # venue-dates that the earlier ones didn't have, so gaps in one feed get covered by the next.
    covered = {}  # (venue, date) -> shows already listed by higher-priority sources

    def already_listed(s):
        for other in covered.get((s["venue"], s["start"][:10]), []):
            a, b = _act_key(s["artist"]), _act_key(other["artist"])
            if s["start"] == other["start"] or a in b or b in a or SequenceMatcher(None, a, b).ratio() > 0.6:
                return True  # same show under a slightly different name, or same slot
        return False

    for prio, (label, fn) in enumerate(SOURCES):
        try:
            got = [s for s in fn() if today <= s["start"][:10] <= horizon and s["artist"]
                   and not already_listed(s)
                   and not NOT_MUSIC.search(f"{s['artist']} {s['tagline']}")
                   and not (_event_key(s.get("url")) and _event_key(s.get("url")) in TM_NOT_MUSIC)]
            for s in got:
                s["id"] = show_id(s)
                s["_prio"] = prio
                slot = (s["venue"], s["start"])
                if VENUE_SIZE.get(s["venue"]) == "large" and slot in big_slots:
                    continue  # same arena show from a second feed
                big_slots.add(slot)
                fresh.setdefault(s["id"], s)  # first source wins on duplicates
            for s in got:
                covered.setdefault((s["venue"], s["start"][:10]), []).append(s)
            report.append(f"  ✓ {label}: {len(got)} shows")
        except Exception as e:  # one broken site shouldn't stop the rest
            report.append(f"  ✗ {label}: {type(e).__name__}: {e}")

    print("\n".join(report))
    report = []
    fresh = drop_cross_venue_duplicates(fresh)
    for s in fresh.values():
        s.pop("_prio", None)
    kept, dropped = curate(list(fresh.values()))
    fresh = {s["id"]: s for s in kept}  # ids stay as collected so saved plans keep matching
    report.append(f"\n  curated: dropped {len(dropped)} non-artist listings (see data/dropped.txt)")
    (ROOT / "data" / "dropped.txt").write_text("\n".join(sorted(set(dropped))) + "\n")
    tagged = tag_shows(list(fresh.values()))
    comics = [k for k, s in fresh.items() if "Comedy" in s["genres"]]
    for k in comics:  # music databases say this performer is a comedian / podcaster, not a musician
        dropped.append(fresh.pop(k)["artist"])
    (ROOT / "data" / "dropped.txt").write_text("\n".join(sorted(set(dropped))) + "\n")
    genre_fixes = {k.lower(): v for k, v in OVERRIDES.get("genres", {}).items()}
    for s in fresh.values():  # Griffin's manual genre calls (collector/overrides.json) beat the databases
        if s["artist"].lower() in genre_fixes:
            s["genres"] = genre_fixes[s["artist"].lower()]
    for s in fresh.values():  # club venues: untagged nights are almost always dance music
        if not s["genres"] and VENUE_GENRE.get(s["venue"]):
            s["genres"] = [VENUE_GENRE[s["venue"]]]
    report.append(f"\n  genres: {tagged}/{len(fresh)} shows tagged")
    report.append(f"  up & coming: {mark_rising(list(fresh.values()), VENUE_SIZE)} shows")
    report.append(f"  funk / disco / groove (outside Dance): {mark_groove(list(fresh.values()))} shows")
    for s in fresh.values():  # manual calls stay final even after the Last.fm passes
        if s["artist"].lower() in genre_fixes:
            s["genres"] = genre_fixes[s["artist"].lower()]

    # keep past shows from earlier runs (history), drop anything stale
    past = [s for s in load_existing() if oldest <= s["start"][:10] < today and s["id"] not in fresh]
    shows = sorted(past + list(fresh.values()), key=lambda s: s["start"])

    OUT.parent.mkdir(exist_ok=True)
    payload = {"updated": now.strftime("%Y-%m-%dT%H:%M"), "venues": VENUES, "shows": shows,
               "outdoorSeason": outdoor_season()}
    OUT.write_text("// Generated by collector/collect.py — do not edit by hand.\nwindow.NIGHT_OUT = "
                   + json.dumps(payload, ensure_ascii=False, indent=0) + ";\n")

    print("\n".join(report + AI_REPORT))
    write_coverage(list(fresh.values()))
    track_venue_health(list(fresh.values()))
    print(f"\n{len(fresh)} upcoming shows (+{len(past)} past) -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
