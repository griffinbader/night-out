// Turns the collector's output (data/shows.js -> window.NIGHT_OUT) into what the app uses.
// Friends come from accounts (account.js).

const BOROUGHS = ['Manhattan', 'Brooklyn', 'Queens', 'Bronx', 'Staten Island'];
const VIBES = ['Intimate', 'Dance all night', 'Sweaty & loud', 'Chill', 'Big room', 'Late night'];


// Small deterministic random helpers (used for artwork and sample friends).
function hashStr(s) {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619);
  return h >>> 0;
}
function rng(seed) {
  let a = hashStr(seed);
  return () => {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const pick = (r, arr) => arr[Math.floor(r() * arr.length)];
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);

const RAW = window.NIGHT_OUT || { venues: [], shows: [], updated: null };
const VENUES = RAW.venues;
const venueById = Object.fromEntries(VENUES.map(v => [v.id, v]));

function vibesFor(show, venue, hour) {
  const vibes = new Set(venue.vibes);
  const g = show.genres.join(' ').toLowerCase();
  if (/dance/.test(g)) vibes.add('Dance all night');
  if (/punk|metal/.test(g)) vibes.add('Sweaty & loud');
  if (/jazz|folk/.test(g)) vibes.add('Chill');
  if (hour >= 22 || hour < 5) vibes.add('Late night'); // 10pm or later, including after-midnight sets
  if (venue.size === 'small' && !vibes.has('Sweaty & loud')) vibes.add('Intimate');
  return [...vibes].slice(0, 3);
}

const SHOWS = RAW.shows
  .filter(s => venueById[s.venue])
  .map(raw => {
    // listing text comes from venue sites, so escape it before it goes into the page
    const s = { ...raw, artist: esc(raw.artist), support: raw.support.map(esc), tagline: esc(raw.tagline),
      image: raw.image && esc(raw.image), url: raw.url && esc(raw.url) };  // genres come from our own fixed list
    const venue = venueById[s.venue];
    const start = new Date(s.start); // local NYC time, e.g. 2026-10-02T20:00
    return {
      ...s,
      venue,
      start,
      vibes: vibesFor(s, venue, start.getHours()),
      description: s.tagline || '',
    };
  })
  .sort((a, b) => a.start - b.start);

// Broad genres, in the order they appear as filters (set in collector/genres.py).
const GENRE_ORDER = ['Pop', 'Rap', 'R&B', 'Indie', 'Rock', 'Punk & Metal', 'Dance', 'Jazz', 'Country & Folk', 'Latin'];
const GENRES = GENRE_ORDER.filter(g => SHOWS.some(s => s.genres.includes(g)));

const UPDATED = RAW.updated ? new Date(RAW.updated) : null;
