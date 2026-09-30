"""Every venue Shindig knows about.

borough / hood power the location filters. size is small (<400), medium (<1000)
or large. vibes are the venue's baseline feel ("Big room" = 2,500+ capacity, "Sitting" = seated shows); shows add more based on time/genre.
lat/lng (from OpenStreetMap) place the venue on the map.
"""

VENUES = [
    # --- Your original list ---
    dict(id="babys", name="Baby's All Right", borough="Brooklyn", hood="Williamsburg", size="small", vibes=["Intimate"], lat=40.70997, lng=-73.96342),
    dict(id="nc101", name="Nightclub 101", borough="Manhattan", hood="East Village", size="small", vibes=["Throw ass"], lat=40.72585, lng=-73.98404),
    dict(id="mercury", name="Mercury Lounge", borough="Manhattan", hood="Lower East Side", size="small", vibes=["Intimate"], lat=40.7221, lng=-73.98679),
    dict(id="bowery", name="Bowery Ballroom", borough="Manhattan", hood="Lower East Side", size="medium", vibes=[], lat=40.72044, lng=-73.99333),
    dict(id="webster", name="Webster Hall", borough="Manhattan", hood="East Village", size="large", vibes=[], lat=40.73176, lng=-73.98909),
    dict(id="irving", name="Irving Plaza", borough="Manhattan", hood="Union Square", size="large", vibes=[], lat=40.73491, lng=-73.98827),
    dict(id="paramount", name="Brooklyn Paramount", borough="Brooklyn", hood="Downtown Brooklyn", size="large", vibes=["Big room"], lat=40.69004, lng=-73.98173),
    dict(id="steel", name="Brooklyn Steel", borough="Brooklyn", hood="East Williamsburg", size="large", vibes=[], lat=40.71939, lng=-73.93875),
    dict(id="lpr", name="LPR", borough="Manhattan", hood="Greenwich Village", size="medium", vibes=[], lat=40.72843, lng=-73.99988),
    dict(id="sultan", name="The Sultan Room", borough="Brooklyn", hood="Bushwick", size="small", vibes=["Intimate"], lat=40.70555, lng=-73.92234),
    dict(id="sultanroof", name="The Sultan Room Rooftop", borough="Brooklyn", hood="Bushwick", size="small", vibes=["Chill"], lat=40.70555, lng=-73.92234),
    dict(id="unionpool", name="Union Pool", borough="Brooklyn", hood="Williamsburg", size="small", vibes=["Sweaty & loud"], lat=40.71565, lng=-73.95199),
    dict(id="bowl", name="Brooklyn Bowl", borough="Brooklyn", hood="Williamsburg", size="medium", vibes=["Throw ass"], lat=40.72205, lng=-73.95755),
    dict(id="mhow", name="Music Hall of Williamsburg", borough="Brooklyn", hood="Williamsburg", size="medium", vibes=[], lat=40.71915, lng=-73.96178),
    dict(id="racket", name="Racket", borough="Manhattan", hood="Chelsea", size="small", vibes=["Sweaty & loud"], lat=40.74305, lng=-74.00574),
    dict(id="gramercy", name="Gramercy Theatre", borough="Manhattan", hood="Gramercy", size="medium", vibes=[], lat=40.73987, lng=-73.98494),
    dict(id="elsewhere", name="Elsewhere", borough="Brooklyn", hood="Bushwick", size="medium", vibes=["Throw ass"], genre="Dance", lat=40.70948, lng=-73.92324),
    dict(id="warsaw", name="Warsaw", borough="Brooklyn", hood="Greenpoint", size="medium", vibes=["Sweaty & loud"], lat=40.72254, lng=-73.94832),

    # --- Added Sept 30 ---
    dict(id="markethotel", name="Market Hotel", borough="Brooklyn", hood="Bushwick", size="medium", vibes=["Sweaty & loud"], lat=40.69693, lng=-73.93459),
    dict(id="sawdust", name="National Sawdust", borough="Brooklyn", hood="Williamsburg", size="small", vibes=["Sitting", "Intimate", "Chill"], lat=40.71897, lng=-73.96124),
    dict(id="publicrecords", name="Public Records", borough="Brooklyn", hood="Gowanus", size="small", vibes=["Throw ass"], genre="Dance", lat=40.68217, lng=-73.98639),
    dict(id="tveye", name="TV Eye", borough="Queens", hood="Ridgewood", size="small", vibes=["Sweaty & loud"], lat=40.69791, lng=-73.90533),
    dict(id="holo", name="H0L0", borough="Queens", hood="Ridgewood", size="small", vibes=["Throw ass"], genre="Dance", lat=40.69428, lng=-73.90218),
    dict(id="sonyhall", name="Sony Hall", borough="Manhattan", hood="Times Square", size="medium", vibes=[], lat=40.75965, lng=-73.98701),

    # --- Added Oct 1 via the SeatGeek API (music venues ~200+ capacity) ---
    dict(id="bluenote", name="Blue Note", borough="Manhattan", hood="Greenwich Village", size="small", vibes=["Sitting", "Intimate", "Chill"], genre="Jazz", lat=40.7309, lng=-74.0007),
    dict(id="palladium", name="Palladium Times Square", borough="Manhattan", hood="Times Square", size="large", vibes=[], lat=40.7576, lng=-73.9858),
    dict(id="pacha", name="Pacha NYC", borough="Manhattan", hood="Hell's Kitchen", size="large", vibes=["Throw ass"], genre="Dance", lat=40.76367, lng=-73.99744),
    dict(id="unitedpalace", name="United Palace", borough="Manhattan", hood="Washington Heights", size="large", vibes=["Sitting", "Big room"], lat=40.8465, lng=-73.9379),
    dict(id="pier17", name="The Rooftop at Pier 17", borough="Manhattan", hood="Seaport", size="large", vibes=["Big room"], lat=40.7063, lng=-74.0038),
    dict(id="storehouse", name="Brooklyn Storehouse", borough="Brooklyn", hood="Navy Yard", size="large", vibes=["Big room", "Throw ass"], genre="Dance", lat=40.6998, lng=-73.9745),
    dict(id="colden", name="Colden Auditorium", borough="Queens", hood="Flushing", size="large", vibes=["Sitting"], lat=40.7498, lng=-73.8187),
    dict(id="lefrak", name="LeFrak Concert Hall", borough="Queens", hood="Flushing", size="medium", vibes=["Sitting", "Chill"], lat=40.7377, lng=-73.8157),
    dict(id="stgeorge", name="St. George Theatre", borough="Staten Island", hood="St. George", size="large", vibes=["Sitting", "Big room"], lat=40.6418, lng=-74.0773),
    dict(id="lehman", name="Lehman Center", borough="Bronx", hood="Bedford Park", size="large", vibes=["Sitting"], lat=40.8749, lng=-73.8932),
    dict(id="citywinery", name="City Winery", borough="Manhattan", hood="Hudson Square", size="medium", vibes=["Sitting", "Intimate", "Chill"], lat=40.7263, lng=-74.006),
    dict(id="bellhouse", name="The Bell House", borough="Brooklyn", hood="Gowanus", size="medium", vibes=[], lat=40.6735, lng=-73.9916),
    dict(id="littlefield", name="Littlefield", borough="Brooklyn", hood="Gowanus", size="small", vibes=["Intimate"], lat=40.67842, lng=-73.98332),
    dict(id="saintvitus", name="Saint Vitus", borough="Brooklyn", hood="Greenpoint", size="small", vibes=["Sweaty & loud"], lat=40.7368, lng=-73.9551),
    dict(id="pioneerworks", name="Pioneer Works", borough="Brooklyn", hood="Red Hook", size="medium", vibes=[], lat=40.6792, lng=-74.0122),
    dict(id="scott99", name="99 Scott", borough="Brooklyn", hood="Bushwick", size="medium", vibes=["Throw ass"], genre="Dance", lat=40.7106, lng=-73.9234),
    dict(id="crownhill", name="Crown Hill Theatre", borough="Brooklyn", hood="Crown Heights", size="medium", vibes=[], lat=40.6731, lng=-73.9504),
    dict(id="roughtrade", name="Rough Trade Below", borough="Manhattan", hood="Midtown", size="small", vibes=["Intimate"], lat=40.75929, lng=-73.97958),
    dict(id="sobs", name="SOB's", borough="Manhattan", hood="Hudson Square", size="medium", vibes=["Throw ass"], lat=40.7285, lng=-74.0051),
    dict(id="xanadu", name="Xanadu", borough="Brooklyn", hood="Bushwick", size="medium", vibes=["Throw ass"], lat=40.72089, lng=-73.95554),
    dict(id="nowadays", name="Nowadays", borough="Queens", hood="Ridgewood", size="medium", vibes=["Throw ass"], genre="Dance", lat=40.6929, lng=-73.9015),
    dict(id="melrose", name="Melrose Ballroom", borough="Queens", hood="Long Island City", size="medium", vibes=[], lat=40.7556, lng=-73.9285),
    dict(id="silo", name="SILO", borough="Brooklyn", hood="Bushwick", size="medium", vibes=["Throw ass"], genre="Dance", lat=40.7105, lng=-73.9229),
    dict(id="basementny", name="Basement", borough="Queens", hood="Maspeth", size="medium", vibes=["Throw ass"], genre="Dance", lat=40.7157, lng=-73.9143),
    dict(id="apollo", name="Apollo Theater", borough="Manhattan", hood="Harlem", size="large", vibes=["Sitting"], lat=40.8097, lng=-73.9496),
    dict(id="ethical", name="NY Society for Ethical Culture", borough="Manhattan", hood="Upper West Side", size="medium", vibes=["Sitting", "Chill"], lat=40.7711, lng=-73.9801),
    dict(id="citifield", name="Citi Field", borough="Queens", hood="Flushing", size="large", vibes=["Big room"], lat=40.7577, lng=-73.8456),

    # --- Other NYC venues that come with the Bowery Presents feed ---
    dict(id="terminal5", name="Terminal 5", borough="Manhattan", hood="Hell's Kitchen", size="large", vibes=["Big room"], lat=40.76975, lng=-73.99274),
    dict(id="knockdown", name="Knockdown Center", borough="Queens", hood="Maspeth", size="large", vibes=["Big room", "Throw ass"], lat=40.71528, lng=-73.91367),
    dict(id="kings", name="Kings Theatre", borough="Brooklyn", hood="Flatbush", size="large", vibes=["Sitting", "Big room"], lat=40.64597, lng=-73.95797),
    dict(id="townhall", name="The Town Hall", borough="Manhattan", hood="Midtown", size="large", vibes=["Sitting", "Chill"], lat=40.75602, lng=-73.98456),
    dict(id="beacon", name="Beacon Theatre", borough="Manhattan", hood="Upper West Side", size="large", vibes=["Sitting", "Big room"], lat=40.78049, lng=-73.98113),
    dict(id="monarch", name="Brooklyn Monarch", borough="Brooklyn", hood="East Williamsburg", size="large", vibes=["Big room"], lat=40.71094, lng=-73.93625),
    dict(id="meadows", name="The Meadows", borough="Brooklyn", hood="East Williamsburg", size="large", vibes=["Big room"], lat=40.71089, lng=-73.93662),
    dict(id="kbridge", name="Under the K Bridge Park", borough="Brooklyn", hood="Greenpoint", size="large", vibes=["Big room"], lat=40.72543, lng=-73.93228),
    dict(id="hammerstein", name="Hammerstein Ballroom", borough="Manhattan", hood="Midtown", size="large", vibes=["Big room"], lat=40.75294, lng=-73.99412),
    dict(id="foresthills", name="Forest Hills Stadium", borough="Queens", hood="Forest Hills", size="large", vibes=["Big room"], lat=40.71986, lng=-73.84676),
    dict(id="flushing", name="Flushing Meadows Corona Park", borough="Queens", hood="Corona", size="large", vibes=["Big room"], lat=40.74057, lng=-73.84283),
    dict(id="barclays", name="Barclays Center", borough="Brooklyn", hood="Prospect Heights", size="large", vibes=["Big room"], lat=40.68251, lng=-73.97525),
    dict(id="msg", name="Madison Square Garden", borough="Manhattan", hood="Midtown", size="large", vibes=["Big room"], lat=40.75051, lng=-73.99352),
    dict(id="msgtheater", name="The Theater at MSG", borough="Manhattan", hood="Midtown", size="large", vibes=["Sitting", "Big room"], lat=40.75051, lng=-73.99352),
    dict(id="radiocity", name="Radio City Music Hall", borough="Manhattan", hood="Midtown", size="large", vibes=["Sitting", "Big room"], lat=40.76013, lng=-73.98002),
    dict(id="carnegie", name="Carnegie Hall", borough="Manhattan", hood="Midtown", size="large", vibes=["Sitting", "Chill"], lat=40.76488, lng=-73.98028),
]

# Bowery Presents names -> our venue ids (NYC five boroughs only).
BOWERY_NAMES = {
    "Webster Hall": "webster", "Brooklyn Steel": "steel", "Racket": "racket",
    "Music Hall of Williamsburg": "mhow", "Terminal 5": "terminal5", "Knockdown Center": "knockdown",
    "Kings Theatre": "kings", "The Town Hall": "townhall", "Beacon Theatre": "beacon",
    "Brooklyn Monarch": "monarch", "The Meadows": "meadows", "Under the K Bridge Park": "kbridge",
    "Hammerstein Ballroom": "hammerstein", "Forest Hills Stadium": "foresthills",
    "Flushing Meadows Corona Park": "flushing", "Barclays Center": "barclays",
    "Madison Square Garden": "msg", "Infosys Theater at Madison Square Garden": "msgtheater",
    "Radio City Music Hall": "radiocity", "Carnegie Hall": "carnegie",
    "Stern Auditorium / Perelman Stage at Carnegie Hall": "carnegie", "The Sultan Room": "sultan", "Elsewhere": "elsewhere",
}

# Ticketmaster Discovery API venue ids -> our venue ids (filled in once we have an API key).
TICKETMASTER_VENUES = {
    "KovZ917AYEJ": "nc101",
    "KovZpaFPje": "irving", "KovZpZA77ldA": "paramount", "KovZpZAdJtAA": "warsaw", "KovZpZAEAdaA": "gramercy",
    "KovZpZAJAkAA": "mercury", "KovZpZA7dkJA": "bowery", "KovZ917Ah5Q": "sonyhall", "KovZ917AtP3": "barclays",
    "KovZpZAkJtvA": "bluenote", "KovZ917ARvk": "bellhouse",
    "KovZpZAFdJtA": "townhall", "KovZpZAIetFA": "bowl", "KovZpZAEAE6A": "hammerstein",
    "KovZpaFtpe": "palladium", "KovZpZAatEFA": "pier17",
    "KovZpZAJEa6A": "kings",
    "KovZ917ARQ0": "lehman", "KovZpZAIdJ1A": "colden", "KovZ917AG0V": "lefrak",
    "KovZpZA7AAEA": "msg", "KovZpZA7kvlA": "msgtheater", "KovZpZAE7vdA": "radiocity", "KovZpZAEAd6A": "beacon",
    "KovZpZA7AAIA": "apollo", "KovZ917AJw7": "apollo", "KovZ917AJsB": "apollo",
    "KovZpa4PZe": "stgeorge", "KovZpZAalvtA": "citifield",
}

# SeatGeek venue ids -> our venue ids (official SeatGeek Platform API, concerts only).
SEATGEEK_VENUES = {3731: "pacha",
                   1410: "unitedpalace",
                   462992: "storehouse",
                   522350: "colden",
                   372451: "lefrak",
                   3086: "lehman",
                   4730: "citywinery",
                   71344: "pioneerworks",
                   450980: "scott99",
                   522178: "crownhill",
                   1609550: "roughtrade",
                   1608343: "xanadu",
                   430407: "nowadays",
                   521776: "silo",
                   467045: "basementny",
                   1366: "ethical",
                   774: "carnegie",
                   994: "carnegie",
                   56718: "babys",
}

# Official websites, used as the link for listings that come from SeatGeek so people
# land on the venue's own page (not a resale marketplace).
VENUE_SITES = {
    "msg": "https://www.msg.com/madison-square-garden", "msgtheater": "https://www.msg.com/the-theater-at-madison-square-garden",
    "radiocity": "https://www.msg.com/radio-city-music-hall", "beacon": "https://www.msg.com/beacon-theatre",
    "babys": "https://babysallright.com/", "pacha": "https://www.pachanyc.com/",
    "unitedpalace": "https://www.unitedpalace.org/", "storehouse": "https://brooklynstorehouse.com/",
    "colden": "https://kupferbergcenter.org/events/", "lefrak": "https://kupferbergcenter.org/events/",
    "stgeorge": "https://stgeorgetheatre.com/events/", "lehman": "https://www.lehmancenter.org/",
    "citywinery": "https://citywinery.com/", "saintvitus": "https://www.saintvitusbar.com/",
    "pioneerworks": "https://pioneerworks.org/", "scott99": "https://www.99scott.com/", "crownhill": "https://crownhilltheatre.com/calendar",
    "roughtrade": "https://www.roughtrade.com/", "xanadu": "https://www.xanadu.nyc/", "nowadays": "https://nowadays.nyc/",
    "silo": "https://www.silo-brooklyn.com/", "basementny": "https://basementny.net/", "apollo": "https://www.apollotheater.org/",
    "ethical": "https://www.ethicalsociety.org/", "citifield": "https://www.mlb.com/mets/tickets/concerts",
    "carnegie": "https://www.carnegiehall.org/calendar",
    "tveye": "https://tveyenyc.com/", "monarch": "https://www.brooklynmonarch.com/", "meadows": "https://www.themeadowsnyc.com/",
    "kbridge": "https://www.underthekbridge.com/", "knockdown": "https://knockdown.center/", "markethotel": "https://www.markethotel.org/calendar",
    "sawdust": "https://www.nationalsawdust.org/performances", "holo": "https://h0l0.nyc/events", "melrose": "https://www.melroseballroom.com/events",
    "unionpool": "https://www.union-pool.com/calendar", "sultan": "https://thesultanroom.com/", "sultanroof": "https://thesultanroom.com/",
    "publicrecords": "https://publicrecords.nyc/", "sobs": "https://sobs.com/", "lpr": "https://lpr.com/", "elsewhere": "https://www.elsewhere.club/events",
    "littlefield": "https://littlefieldnyc.com/all-shows/", "flushing": "https://www.nycgovparks.org/parks/flushing-meadows-corona-park",
    "irving": "https://www.irvingplaza.com/", "paramount": "https://www.brooklynparamount.com/", "warsaw": "https://www.warsawconcerts.com/",
    "gramercy": "https://www.thegramercytheatre.com/", "mercury": "https://mercuryeastpresents.com/mercurylounge/",
    "bowery": "https://mercuryeastpresents.com/boweryballroom/", "webster": "https://websterhall.com/",
    "steel": "https://www.bowerypresents.com/brooklyn-steel/", "mhow": "https://www.bowerypresents.com/music-hall-of-williamsburg/",
    "racket": "https://racketnyc.com/", "terminal5": "https://www.terminal5nyc.com/", "bowl": "https://www.brooklynbowl.com/brooklyn/shows/all",
    "kings": "https://www.kingstheatre.com/", "townhall": "https://thetownhall.org/", "hammerstein": "https://www.mcstudios.com/hammerstein-ballroom",
    "barclays": "https://www.barclayscenter.com/events", "bluenote": "https://www.bluenotejazz.com/nyc/",
    "palladium": "https://www.palladiumtimessquare.com/", "pier17": "https://rooftopatpier17.com/", "sonyhall": "https://sonyhall.com/shows/",
    "bellhouse": "https://www.thebellhouseny.com/", "nc101": "https://www.nightclub101.com/", "foresthills": "https://foresthillsstadium.com/",
    "saintvitus": "https://www.saintvitusbar.com/",
}

# Venues the new-venue watch should never suggest: closed, turned down, not music venues, or outside NYC.
IGNORED_CANDIDATES = {
    "cielo", "cuttingroom", "drom", "boweryelectric", "rockwoodmusichall", "jazzatlincolncenter", "nebula",
    "superioringredients", "230 5thave", "2305thave", "booththeatre", "palacetheatreny", "54below",
    "loewsjerseytheatre", "williamscenter", "bergenperformingartscenter", "centralparkwollmanrink",
}

# Outdoor / seasonal venues: months without shows are normal, so the closing watch ignores quiet stretches.
SEASONAL_VENUES = {"foresthills", "pier17", "meadows", "kbridge", "flushing", "citifield"}
