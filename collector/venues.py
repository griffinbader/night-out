"""Every venue Shindig knows about.

borough / hood power the location filters. size is small (<400), medium (<1000)
or large. vibes are the venue's baseline feel; shows add more based on time/genre.
lat/lng (from OpenStreetMap) place the venue on the map.
"""

VENUES = [
    # --- Your original list ---
    dict(id="babys", name="Baby's All Right", borough="Brooklyn", hood="Williamsburg", size="small", vibes=["Intimate"], lat=40.70997, lng=-73.96342),
    dict(id="nc101", name="Nightclub 101", borough="Manhattan", hood="East Village", size="small", vibes=["Dance all night", "Late night"], lat=40.72585, lng=-73.98404),
    dict(id="mercury", name="Mercury Lounge", borough="Manhattan", hood="Lower East Side", size="small", vibes=["Intimate"], lat=40.7221, lng=-73.98679),
    dict(id="bowery", name="Bowery Ballroom", borough="Manhattan", hood="Lower East Side", size="medium", vibes=[], lat=40.72044, lng=-73.99333),
    dict(id="webster", name="Webster Hall", borough="Manhattan", hood="East Village", size="large", vibes=["Big room"], lat=40.73176, lng=-73.98909),
    dict(id="irving", name="Irving Plaza", borough="Manhattan", hood="Union Square", size="large", vibes=["Big room"], lat=40.73491, lng=-73.98827),
    dict(id="paramount", name="Brooklyn Paramount", borough="Brooklyn", hood="Downtown Brooklyn", size="large", vibes=["Big room"], lat=40.69004, lng=-73.98173),
    dict(id="steel", name="Brooklyn Steel", borough="Brooklyn", hood="East Williamsburg", size="large", vibes=["Big room"], lat=40.71939, lng=-73.93875),
    dict(id="lpr", name="LPR", borough="Manhattan", hood="Greenwich Village", size="medium", vibes=[], lat=40.72843, lng=-73.99988),
    dict(id="sultan", name="The Sultan Room", borough="Brooklyn", hood="Bushwick", size="small", vibes=["Intimate"], lat=40.70555, lng=-73.92234),
    dict(id="sultanroof", name="The Sultan Room Rooftop", borough="Brooklyn", hood="Bushwick", size="small", vibes=["Chill"], lat=40.70555, lng=-73.92234),
    dict(id="unionpool", name="Union Pool", borough="Brooklyn", hood="Williamsburg", size="small", vibes=["Sweaty & loud", "Late night"], lat=40.71565, lng=-73.95199),
    dict(id="bowl", name="Brooklyn Bowl", borough="Brooklyn", hood="Williamsburg", size="medium", vibes=["Dance all night"], lat=40.72205, lng=-73.95755),
    dict(id="mhow", name="Music Hall of Williamsburg", borough="Brooklyn", hood="Williamsburg", size="medium", vibes=[], lat=40.71915, lng=-73.96178),
    dict(id="racket", name="Racket", borough="Manhattan", hood="Chelsea", size="small", vibes=["Sweaty & loud"], lat=40.74305, lng=-74.00574),
    dict(id="gramercy", name="Gramercy Theatre", borough="Manhattan", hood="Gramercy", size="medium", vibes=[], lat=40.73987, lng=-73.98494),
    dict(id="elsewhere", name="Elsewhere", borough="Brooklyn", hood="Bushwick", size="medium", vibes=["Dance all night", "Late night"], genre="Dance", lat=40.70948, lng=-73.92324),
    dict(id="warsaw", name="Warsaw", borough="Brooklyn", hood="Greenpoint", size="medium", vibes=["Sweaty & loud"], lat=40.72254, lng=-73.94832),

    # --- Added Sept 30 ---
    dict(id="markethotel", name="Market Hotel", borough="Brooklyn", hood="Bushwick", size="medium", vibes=["Sweaty & loud", "Late night"], lat=40.69693, lng=-73.93459),
    dict(id="sawdust", name="National Sawdust", borough="Brooklyn", hood="Williamsburg", size="small", vibes=["Intimate", "Chill"], lat=40.71897, lng=-73.96124),
    dict(id="publicrecords", name="Public Records", borough="Brooklyn", hood="Gowanus", size="small", vibes=["Dance all night", "Late night"], genre="Dance", lat=40.68217, lng=-73.98639),
    dict(id="tveye", name="TV Eye", borough="Queens", hood="Ridgewood", size="small", vibes=["Sweaty & loud", "Late night"], lat=40.69791, lng=-73.90533),
    dict(id="holo", name="H0L0", borough="Queens", hood="Ridgewood", size="small", vibes=["Dance all night", "Late night"], genre="Dance", lat=40.69428, lng=-73.90218),
    dict(id="sonyhall", name="Sony Hall", borough="Manhattan", hood="Times Square", size="medium", vibes=[], lat=40.75965, lng=-73.98701),

    # --- Other NYC venues that come with the Bowery Presents feed ---
    dict(id="terminal5", name="Terminal 5", borough="Manhattan", hood="Hell's Kitchen", size="large", vibes=["Big room"], lat=40.76975, lng=-73.99274),
    dict(id="knockdown", name="Knockdown Center", borough="Queens", hood="Maspeth", size="large", vibes=["Big room", "Dance all night"], lat=40.71528, lng=-73.91367),
    dict(id="kings", name="Kings Theatre", borough="Brooklyn", hood="Flatbush", size="large", vibes=["Big room"], lat=40.64597, lng=-73.95797),
    dict(id="townhall", name="The Town Hall", borough="Manhattan", hood="Midtown", size="large", vibes=["Chill"], lat=40.75602, lng=-73.98456),
    dict(id="beacon", name="Beacon Theatre", borough="Manhattan", hood="Upper West Side", size="large", vibes=["Big room"], lat=40.78049, lng=-73.98113),
    dict(id="monarch", name="Brooklyn Monarch", borough="Brooklyn", hood="East Williamsburg", size="large", vibes=["Big room"], lat=40.71094, lng=-73.93625),
    dict(id="meadows", name="The Meadows", borough="Brooklyn", hood="East Williamsburg", size="large", vibes=["Big room"], lat=40.71089, lng=-73.93662),
    dict(id="kbridge", name="Under the K Bridge Park", borough="Brooklyn", hood="Greenpoint", size="large", vibes=["Big room"], lat=40.72543, lng=-73.93228),
    dict(id="hammerstein", name="Hammerstein Ballroom", borough="Manhattan", hood="Midtown", size="large", vibes=["Big room"], lat=40.75294, lng=-73.99412),
    dict(id="foresthills", name="Forest Hills Stadium", borough="Queens", hood="Forest Hills", size="large", vibes=["Big room"], lat=40.71986, lng=-73.84676),
    dict(id="flushing", name="Flushing Meadows Corona Park", borough="Queens", hood="Corona", size="large", vibes=["Big room"], lat=40.74057, lng=-73.84283),
    dict(id="barclays", name="Barclays Center", borough="Brooklyn", hood="Prospect Heights", size="large", vibes=["Big room"], lat=40.68251, lng=-73.97525),
    dict(id="msg", name="Madison Square Garden", borough="Manhattan", hood="Midtown", size="large", vibes=["Big room"], lat=40.75051, lng=-73.99352),
    dict(id="msgtheater", name="The Theater at MSG", borough="Manhattan", hood="Midtown", size="large", vibes=["Big room"], lat=40.75051, lng=-73.99352),
    dict(id="radiocity", name="Radio City Music Hall", borough="Manhattan", hood="Midtown", size="large", vibes=["Big room"], lat=40.76013, lng=-73.98002),
    dict(id="carnegie", name="Carnegie Hall", borough="Manhattan", hood="Midtown", size="large", vibes=["Chill"], lat=40.76488, lng=-73.98028),
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
    "Stern Auditorium / Perelman Stage at Carnegie Hall": "carnegie", "The Sultan Room": "sultan",
}

# Ticketmaster Discovery API venue ids -> our venue ids (filled in once we have an API key).
TICKETMASTER_VENUES = {}
