"""Keeps Shindig strictly about artists: every listing must headline a specific
artist, band or DJ — no parties, themed nights, talks, kids' shows, comedy,
film-with-orchestra nights, etc. Also pulls the real artist name out of
"An Evening with…", "Grammy-Winning…", "…World Tour" style billing.

Rules handle most cases; overrides.json handles the judgment calls
(exclude a listing, or say who the artist is).
"""

import json
import re
from pathlib import Path

OVERRIDES = json.loads((Path(__file__).parent / "overrides.json").read_text())

# ------------------------------------------------------------ headline cleanup

REWRITES = [
    # "An Evening with X", "A New York Evening With X", "An Intimate Evening With X", "An Evening of Mud with X"
    (r"^(?:an?\s+)?(?:new york\s+|intimate\s+|special\s+|acoustic\s+)?(?:evening|night)\s+(?:of\s+[\w' ]+?\s+)?with\s+(.+)$", r"\1"),
    # "Murmrr Presents Numero Group", "New Amsterdam presents Charlotte Greve"
    (r"^.{2,60}?\s+presents?\s+(.+)$", r"\1"),
    # "20 Years of Nekrogoblikon"
    (r"^\d+\s+years\s+of\s+(.+)$", r"\1"),
    # "X Performs Feels Live", "The Blasting Company plays Over The Garden Wall"
    (r"^(.+?)\s+(?:performs|performing|plays)\s+.+$", r"\1"),
    # "Grammy-Winning ARKAI", "Legendary X"
    (r"^(?:grammy[- ](?:winning|nominated|award[- ]winning)|legendary|the legendary|iconic)\s+(.+)$", r"\1"),
    # leading year: "2026 tripleS World Tour"
    (r"^20\d\d\s+(.+)$", r"\1"),
    # "Zoso The Ultimate Led Zeppelin Experience"
    (r"^(.+?)\s+(?:-\s+)?the ultimate .+ experience$", r"\1"),
]

# Guests / openers written into the headline
GUESTS = re.compile(r"\s+(?:w/ surprise guests?|with surprise guests?|with special guests?|w/ special guests?|with support from|w/|with)\s+", re.I)

TOUR_CUTS = [
    r"\s*[–—]\s*.*\btour\b.*$",                 # "Grace Enger– The Satisfied Girl Tour"
    r"\s+-\s+.*\btour\b.*$",
    r"\s*['\"“‘].*\btour\b.*$",                 # "THE BOUNCING SOULS 'Born To Be Tour'"
    r"\.\s+.*\btour\b.*$",                     # "Bolden. Who you really are. Tour 2026." (not "Rev. Vince")
    r"(?:\s+(?:20\d\d|'\d\d|fall|spring|summer|winter|world|north american?|us|usa|headline|headlining|"
    r"co-headliner?|european|farewell|reunion|anniversary|album|release))*\s+tour\b.*$",
    r"\s+on tour$",
    r"\s+live(?:\s+in\s+[\w ]+|\s+20\d\d)?$",   # "Giles Corey Live in New York"
    r"\s+album release\b.*$",                   # "THE CENTRAL PARK FIVE Album Release presented by …"
    r"\s+\|\s+.*$",                              # "Allan Rayman | HOTEL ALLAN"
    r"\s+[–—-]\s+.*$",                            # "Parachute – The Way it Was", "The Wrecks - Finally"
    r"\s*[“\"].*$",                               # 'Bit Brigade "The Legend of Zelda" + …'
    r"\s*\[[^\]]*\]\s*$",                          # "Croz Boyce [Avey Tare and Geologist …]"
    r"\s+20\d\d(?:/20\d\d)?$",                    # "Madds Buckley 2026/2027"
]

STRIP = re.compile(
    r"\s*[\(\[][^)\]]*(?:set|release|solo|18\+|21\+|all ages|album|ep\b|show|party|tour|live|sold out|night \d|band|performing|presented)[^)\]]*[\)\]]"
    r"|\s*\([^)]*$"                             # dangling "(presented by the J…"
    r"|\s+(?:solo|live!?|in nyc|nyc)$",
    re.I,
)


def headliner(name):
    n = name.strip()
    for pat, repl in REWRITES:
        new = re.sub(pat, repl, n, flags=re.I).strip()
        if new and new != n:
            n = new
    prev = None
    while prev != n:  # strip repeatedly: "X (Solo) Live 2026 Tour"
        prev = n
        n = STRIP.sub("", n).strip(" -–:/|,")
        for cut in TOUR_CUTS:
            new = re.sub(cut, "", n, flags=re.I).strip(" -–:/|,.")
            if new:
                n = new
    return n or name


def split_feat(name):
    """'Osees ft. Brigid Dawson' / 'confetti x khel' / 'ARKAI w/ surprise guest Lindsey Stirling'
    -> ('Osees', ['Brigid Dawson'])."""
    parts = re.split(r"\s+(?:ft\.?|feat\.?|featuring)\s+|\s+x\s+|\s+/\s+|" + GUESTS.pattern, name, flags=re.I)
    return parts[0].strip(), [p.strip() for p in parts[1:] if p.strip()]


# ------------------------------------------------------------ not-an-artist filter

NOT_ARTIST = re.compile(
    r"\bpart(?:y|ies)\b|\bnite\b|takes over|launch|halloween|masquerade|monster mash|"
    r"\b(?:emo|disco|dance|cover|afrobeat|reggaet[oó]n|salsa|goth|80'?s|90'?s|y2k|2000'?s|2010'?s|trance)\s+(?:nights?|nite|party|bro)\b|"
    r"karaoke|open mic|talent show|sound ?bath|run club|\b5k\b|listening (?:party|session|happy hour)|happy hour|"
    r"record fair|vinyl night|records and stories|book (?:signing|talk|launch)|in conversation|podcast|radio hour|"
    r"\bdrag\b|king of drag|burlesque|for kids|rock and roll playhouse|little spoon|\bin concert\b|concert tour$|"
    r"\bfilm\b|movie|pop-?up|anniversary(?! tour)|workshop|line dancing|barre\b|comedy|comedian|live taping|"
    r"women.s game|freeski|rocket science|\bsalon\b|premiere|a new musical|\bmusical\b|winter festival|"
    r"\bgala\b|benefit(?:ing)?\b|fundraiser|modular society|shagshop|club 1bd|9am banger|revelation nights|"
    r"back to the \d0s|candlelight|tribute night|\bthe \d0'?s\b|music festival|\bshowcase\b|for families|"
    r"^x\s|\bkoom\b|\bconference\b|\bsummit\b|takeover|orchestra concert|symphonic (?:tribute|tour)|video game|\bin concert\b",
    re.I,
)

# Subtitles are often album/tour names ("20th Anniversary of …", "Record Premiere Celebration"),
# so only unmistakable non-music words there count against a listing.
NOT_ARTIST_SUBTITLE = re.compile(
    r"\bpart(?:y|ies)\b|podcast|comedy|comedian|live taping|for kids|rock and roll playhouse|listening (?:session|party)|"
    r"in conversation|book (?:signing|talk|launch)|country line dancing|drag show|burlesque|\btributes\b|"
    r"\b(?:metal|metalcore|emo|disco|goth|dance|soul|house|techno|\d0s|y2k)\s+night\b|takeover|all day long",
    re.I,
)


def _key(s):
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def curate(shows, log=print):
    """Rewrites headliners and drops non-artist listings, in place. Returns (kept, dropped)."""
    exclude = [_key(x) for x in OVERRIDES["exclude"]]
    rename = {_key(k): v for k, v in OVERRIDES["rename"].items()}
    keep, dropped = [], []
    for s in shows:
        raw = s["artist"]
        k = _key(raw)
        hit = rename.get(k) or next((v for rk, v in rename.items() if k.startswith(rk)), None)
        if hit:
            s["artist"] = hit
            k = next(rk for rk in rename if k.startswith(rk) or rk == k)
        else:
            head, feat = split_feat(headliner(raw))
            s["artist"], s["support"] = head, feat + s["support"]
        presenter = re.fullmatch(r"(.{2,40}?)\s+presents?", s.get("tagline", "") or "", re.I)
        if presenter and re.search(r"\btour\b", raw, re.I) and k not in rename:
            s["artist"], s["tagline"] = presenter.group(1), raw  # "The Self Titled Tour" / "Stephen Day Presents"
        s["support"] = [headliner(x) for x in s["support"] if x and not re.search(r"\btour\b|\bpresents?\b|hosted by|under \d", x, re.I)]
        if re.fullmatch(r"(?:an?\s+)?(?:\w+\s+)?(?:evening|night)", s["artist"], re.I) and s["support"]:
            s["artist"] = s["support"].pop(0)  # "An Evening" + ["Lambchop"] -> Lambchop
        blob = f"{raw} {s.get('tagline', '')}"
        rule_hit = NOT_ARTIST.search(raw) or NOT_ARTIST_SUBTITLE.search(s.get("tagline", ""))
        if any(x and x in _key(blob) for x in exclude) or (k not in rename and rule_hit):
            dropped.append(raw)
            continue
        keep.append(s)
    return keep, dropped
