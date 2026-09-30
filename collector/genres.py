"""Genre tagging: looks artists up on MusicBrainz (then Last.fm) and sorts their tags into
Shindig's genre filters. Results are cached in data/genre_cache.json so each
artist is only looked up once (MusicBrainz allows ~1 request per second).
"""

import json
import os
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "genre_cache.json"
UA = "Shindig/0.1 ( griffin@ctownsounds.com )"  # MusicBrainz asks for a contact

# Shindig genre -> keywords found in MusicBrainz/venue tags. Kept deliberately
# broad (Griffin's call): subgenres fold into ~10 filters people actually use.
# First match wins per tag, so more specific keywords sit higher up.
BUCKETS = [
    ("Punk & Metal", ["metal", "doom", "sludge", "grindcore", "djent", "deathcore", "metalcore", "punk",
                      "hardcore", "emo", "screamo", "oi", "riot grrrl", "post-hardcore", "ska"]),
    ("Rap", ["hip hop", "hip-hop", "rap", "trap", "drill", "grime", "boom bap"]),
    ("R&B", ["r&b", "rnb", "soul", "neo soul", "gospel", "motown", "quiet storm"]),
    ("Jazz", ["jazz", "funk", "jam band", "jam", "bebop", "swing", "fusion", "afrobeat", "blues"]),
    ("Dance", ["electronic", "electronica", "house", "techno", "edm", "dubstep", "drum and bass", "dnb",
               "garage", "breakbeat", "trance", "idm", "synthwave", "dance", "disco", "club", "bass", "ambient"]),
    ("Latin", ["latin", "reggaeton", "cumbia", "salsa", "bachata", "corrido", "regional mexican", "bossa",
               "tango", "guarachero", "dembow", "brazilian", "mpb"]),
    ("Country & Folk", ["folk", "country", "americana", "bluegrass", "singer-songwriter", "acoustic", "alt-country"]),
    ("Indie", ["indie", "shoegaze", "dream pop", "lo-fi", "bedroom pop", "slowcore", "jangle", "chamber pop",
               "twee", "experimental", "noise", "post-rock", "art rock", "avant-garde"]),
    ("Pop", ["pop", "k-pop", "j-pop", "synthpop", "electropop", "dance-pop", "hyperpop"]),
    ("Rock", ["rock", "grunge", "psychedelic", "stoner", "surf", "new wave", "post-punk", "britpop"]),
]
GENRES = [b for b, _ in BUCKETS]


def bucket_for(tag):
    t = tag.lower()
    for name, words in BUCKETS:
        if any(re.search(rf"(^|[^a-z]){re.escape(w)}([^a-z]|$)", t) for w in words):
            return name
    return None


NOT_MUSIC_TAG = re.compile(r"comedy|comedian|stand-?up|spoken word|podcast|storytelling|improv|sketch|audiobook", re.I)


def bucketize(tags):
    """[(tag, weight)] -> top 2 Shindig genres. Performers whose main tag is comedy etc. get none."""
    if tags and NOT_MUSIC_TAG.search(max(tags, key=lambda t: t[1])[0]):
        return []
    score = {}
    for tag, weight in tags:
        b = bucket_for(tag)
        if b:
            score[b] = score.get(b, 0) + max(weight, 1)
    return [b for b, _ in sorted(score.items(), key=lambda kv: -kv[1])][:2]


# ------------------------------------------------------------ name cleanup

NOISE = re.compile(
    r"\b(20\d\d(/20\d\d)?|north american|world|us|uk|european|headline|fall|spring|summer|winter)\b.*\btour\b.*$"
    r"|\b(tour|live|in concert|album release|record release|release (show|party)|residency|night \d+|early show|late show)\b.*$",
    re.I,
)


def clean_name(name):
    name = re.split(r"\s+[|~]\s+|\s+presents?\s*[:\-]?\s*$|\.\s", name, flags=re.I)[0]
    name = NOISE.sub("", name)
    name = re.sub(r"\((solo|w/ band|full band|dj set|acoustic|live)[^)]*\)", "", name, flags=re.I)
    return re.sub(r"\s+", " ", name).strip(" -–:,(")


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower().replace("&", "and"))


# ------------------------------------------------------------ MusicBrainz

_last_call = [0.0]


def musicbrainz_tags(name):
    wait = 1.1 - (time.time() - _last_call[0])
    if wait > 0:
        time.sleep(wait)
    _last_call[0] = time.time()
    q = urllib.parse.urlencode({"query": f'artist:"{name}"', "fmt": "json", "limit": 5})
    req = urllib.request.Request("https://musicbrainz.org/ws/2/artist/?" + q, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        results = json.load(r).get("artists", [])
    # exact name match only — close-but-wrong artists would give wrong genres
    for a in results:
        if _norm(a["name"]) == _norm(name) or any(_norm(x.get("name", "")) == _norm(name) for x in a.get("aliases", [])):
            return [(t["name"], t.get("count", 1)) for t in a.get("tags", [])]
    return []


# ------------------------------------------------------------ Last.fm

def lastfm_key():
    """API key: LASTFM_API_KEY env var (GitHub Actions secret) or .env locally (never committed)."""
    if os.environ.get("LASTFM_API_KEY"):
        return os.environ["LASTFM_API_KEY"]
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("LASTFM_API_KEY="):
                return line.split("=", 1)[1].strip()
    return None


def lastfm_tags(name, key):
    time.sleep(0.25)  # stay well under Last.fm's rate limit
    q = urllib.parse.urlencode({"method": "artist.gettoptags", "artist": name, "api_key": key,
                                "format": "json", "autocorrect": 0})
    req = urllib.request.Request("https://ws.audioscrobbler.com/2.0/?" + q, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.load(r)
    tags = (data.get("toptags") or {}).get("tag") or []
    # counts are 0-100 relative to the top tag; ignore the long tail of one-off tags
    return [(t["name"], int(t.get("count", 0))) for t in tags if int(t.get("count", 0)) >= 10]


def load_cache():
    return json.loads(CACHE.read_text()) if CACHE.exists() else {}


def save_cache(cache):
    CACHE.parent.mkdir(exist_ok=True)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1, sort_keys=True))


def lookup(name, cache, fm_key=None):
    """Shindig genres for one artist: MusicBrainz first, then Last.fm.
    Each source's answer is cached separately so we never re-ask."""
    key = clean_name(name)
    if not key or len(key) < 2:
        return []
    if key not in cache:
        try:
            cache[key] = bucketize(musicbrainz_tags(key))
        except Exception:
            return []  # network hiccup: don't cache, try again next run
    if cache[key] or not fm_key:
        return cache[key]
    fm = "lastfm:" + key
    if fm not in cache:
        try:
            cache[fm] = bucketize(lastfm_tags(key, fm_key))
        except Exception:
            return []
    return cache[fm]


def tag_shows(shows, log=print):
    """Fill in show['genres'] for every show. Order: venue-provided genres,
    then headliner on MusicBrainz, then the first couple of openers."""
    cache = load_cache()
    fm_key = lastfm_key()
    if not fm_key:
        log("  (no LASTFM_API_KEY in .env — using MusicBrainz only)")
    todo = {clean_name(s["artist"]) for s in shows} - set(cache)
    if todo:
        log(f"  looking up ~{len(todo)} new artists on MusicBrainz (~{len(todo) * 1.1 / 60:.0f}+ min, first run only)…")
    tagged = 0
    for i, s in enumerate(shows):
        venue_tags = bucketize([(g, 3) for g in s.get("genres", [])])
        genres = venue_tags or lookup(s["artist"], cache, fm_key)
        if not genres:
            for opener in s["support"][:2]:
                genres = lookup(opener, cache, fm_key)
                if genres:
                    break
        s["genres"] = genres
        tagged += bool(genres)
        if i % 50 == 0:
            save_cache(cache)  # keep progress if interrupted
    save_cache(cache)
    return tagged
