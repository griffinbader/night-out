"""Every venue Shindig knows about.

borough / hood power the location filters. size is small (<400), medium (<1000)
or large. vibes are the venue's baseline feel; shows add more based on time/genre.
"""

VENUES = [
    # --- Your original list ---
    dict(id="babys", name="Baby's All Right", borough="Brooklyn", hood="Williamsburg", size="small", vibes=["Intimate"]),
    dict(id="nc101", name="Nightclub 101", borough="Manhattan", hood="East Village", size="small", vibes=["Dance all night", "Late night"]),
    dict(id="mercury", name="Mercury Lounge", borough="Manhattan", hood="Lower East Side", size="small", vibes=["Intimate"]),
    dict(id="bowery", name="Bowery Ballroom", borough="Manhattan", hood="Lower East Side", size="medium", vibes=[]),
    dict(id="webster", name="Webster Hall", borough="Manhattan", hood="East Village", size="large", vibes=["Big room"]),
    dict(id="irving", name="Irving Plaza", borough="Manhattan", hood="Union Square", size="large", vibes=["Big room"]),
    dict(id="paramount", name="Brooklyn Paramount", borough="Brooklyn", hood="Downtown Brooklyn", size="large", vibes=["Big room"]),
    dict(id="steel", name="Brooklyn Steel", borough="Brooklyn", hood="East Williamsburg", size="large", vibes=["Big room"]),
    dict(id="lpr", name="LPR", borough="Manhattan", hood="Greenwich Village", size="medium", vibes=[]),
    dict(id="sultan", name="The Sultan Room", borough="Brooklyn", hood="Bushwick", size="small", vibes=["Intimate"]),
    dict(id="sultanroof", name="The Sultan Room Rooftop", borough="Brooklyn", hood="Bushwick", size="small", vibes=["Chill"]),
    dict(id="unionpool", name="Union Pool", borough="Brooklyn", hood="Williamsburg", size="small", vibes=["Sweaty & loud", "Late night"]),
    dict(id="bowl", name="Brooklyn Bowl", borough="Brooklyn", hood="Williamsburg", size="medium", vibes=["Dance all night"]),
    dict(id="mhow", name="Music Hall of Williamsburg", borough="Brooklyn", hood="Williamsburg", size="medium", vibes=[]),
    dict(id="racket", name="Racket", borough="Manhattan", hood="Chelsea", size="small", vibes=["Sweaty & loud"]),
    dict(id="gramercy", name="Gramercy Theatre", borough="Manhattan", hood="Gramercy", size="medium", vibes=[]),
    dict(id="elsewhere", name="Elsewhere", borough="Brooklyn", hood="Bushwick", size="medium", vibes=["Dance all night", "Late night"]),
    dict(id="warsaw", name="Warsaw", borough="Brooklyn", hood="Greenpoint", size="medium", vibes=["Sweaty & loud"]),

    # --- Other NYC venues that come with the Bowery Presents feed ---
    dict(id="terminal5", name="Terminal 5", borough="Manhattan", hood="Hell's Kitchen", size="large", vibes=["Big room"]),
    dict(id="knockdown", name="Knockdown Center", borough="Queens", hood="Maspeth", size="large", vibes=["Big room", "Dance all night"]),
    dict(id="kings", name="Kings Theatre", borough="Brooklyn", hood="Flatbush", size="large", vibes=["Big room"]),
    dict(id="townhall", name="The Town Hall", borough="Manhattan", hood="Midtown", size="large", vibes=["Chill"]),
    dict(id="beacon", name="Beacon Theatre", borough="Manhattan", hood="Upper West Side", size="large", vibes=["Big room"]),
    dict(id="monarch", name="Brooklyn Monarch", borough="Brooklyn", hood="East Williamsburg", size="large", vibes=["Big room"]),
    dict(id="meadows", name="The Meadows", borough="Brooklyn", hood="East Williamsburg", size="large", vibes=["Big room"]),
    dict(id="kbridge", name="Under the K Bridge Park", borough="Brooklyn", hood="Greenpoint", size="large", vibes=["Big room"]),
    dict(id="hammerstein", name="Hammerstein Ballroom", borough="Manhattan", hood="Midtown", size="large", vibes=["Big room"]),
    dict(id="foresthills", name="Forest Hills Stadium", borough="Queens", hood="Forest Hills", size="large", vibes=["Big room"]),
    dict(id="flushing", name="Flushing Meadows Corona Park", borough="Queens", hood="Corona", size="large", vibes=["Big room"]),
    dict(id="barclays", name="Barclays Center", borough="Brooklyn", hood="Prospect Heights", size="large", vibes=["Big room"]),
    dict(id="msg", name="Madison Square Garden", borough="Manhattan", hood="Midtown", size="large", vibes=["Big room"]),
    dict(id="msgtheater", name="The Theater at MSG", borough="Manhattan", hood="Midtown", size="large", vibes=["Big room"]),
    dict(id="radiocity", name="Radio City Music Hall", borough="Manhattan", hood="Midtown", size="large", vibes=["Big room"]),
    dict(id="carnegie", name="Carnegie Hall", borough="Manhattan", hood="Midtown", size="large", vibes=["Chill"]),
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
