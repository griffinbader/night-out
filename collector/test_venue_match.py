"""Guard against filing shows under the wrong venue. Runs before every collection; a failure stops the run
so nothing wrong gets published. Add any misattribution ever found to NEVER_MATCH."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import collect  # noqa: E402
from venues import SEATGEEK_VENUES, TICKETMASTER_VENUES, VENUE_NAMES, VENUES  # noqa: E402

# Real neighbors / other rooms that were once misattributed, or easily could be.
NEVER_MATCH = [
    "Daryl Roth Theatre", "Berlin", "Berlin NYC", "Cafe Wha?", "The Bitter End", "Bleecker Bell",
    "Bleecker Event Hall", "Drom", "Magic Mike Theater New York City", "Brooklyn", "New York", "Manhattan",
    "The Chocolate Factory - Brooklyn", "Hard Rock Cafe", "Manhattan Center Grand Ballroom",
    "Manhattan Center's Grand Ballroom (7th Fl.)", "Kingdom Bound", "Groove", "The Greene Space",
    "INKwell Club at Harbor NYC Rooftop", "Palace Theatre - New York", "Brooklyn Made", "Brooklyn Bowl Philadelphia",
    "Webster Hall Studio", "Blue Note Napa", "Terminal 5 Chicago", "Mercury Ballroom", "Irving Plaza Bar",
]

# Every exact name must point at a real venue, and at most one venue.
ids = {v["id"] for v in VENUES}
bad = [k for k, v in {**VENUE_NAMES}.items() if v not in ids]
bad += [f"TM {k}" for k, v in TICKETMASTER_VENUES.items() if v not in ids]
bad += [f"SG {k}" for k, v in SEATGEEK_VENUES.items() if v not in ids]
wrong = [n for n in NEVER_MATCH if collect._our_venue(n, 40.73, -73.99)]
far = collect._our_venue("Irving Plaza", 40.0, -75.0)  # right name, wrong city
if bad or wrong or far:
    print("VENUE MATCH TEST FAILED")
    print("  unknown venue ids:", bad)
    print("  neighbors that matched one of our venues:", [(n, collect._our_venue(n, 40.73, -73.99)) for n in wrong])
    print("  far-away same-name match:", far)
    sys.exit(1)
print(f"venue match test passed ({len(NEVER_MATCH)} neighbor names rejected, {len(collect.EXACT_VENUE_NAMES)} exact names)")
