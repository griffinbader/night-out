// Turns the collector's output (data/shows.js -> window.NIGHT_OUT) into what the app uses.
// Shows and venues are real. Friends are still sample people until accounts exist.

const BOROUGHS = ['Manhattan', 'Brooklyn', 'Queens', 'Bronx', 'Staten Island'];
const VIBES = ['Intimate', 'Dance all night', 'Sweaty & loud', 'Chill', 'Big room', 'Late night'];

const FRIENDS = [
  { id: 'maya', name: 'Maya', color: '#ff9ccf' },
  { id: 'jordan', name: 'Jordan', color: '#22c07a' },
  { id: 'sam', name: 'Sam', color: '#ffd23f' },
  { id: 'priya', name: 'Priya', color: '#b8a2ff' },
  { id: 'leo', name: 'Leo', color: '#6f86ff' },
  { id: 'tasha', name: 'Tasha', color: '#ff9f1c' },
];

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
  if (/electronic|house|techno|dance|club/.test(g)) vibes.add('Dance all night');
  if (/punk|metal|hardcore|garage/.test(g)) vibes.add('Sweaty & loud');
  if (/jazz|folk|ambient|classical|acoustic/.test(g)) vibes.add('Chill');
  if (hour >= 22) vibes.add('Late night');
  if (venue.size === 'small' && !vibes.has('Sweaty & loud')) vibes.add('Intimate');
  return [...vibes].slice(0, 3);
}

const SHOWS = RAW.shows
  .filter(s => venueById[s.venue])
  .map(raw => {
    // listing text comes from venue sites, so escape it before it goes into the page
    const s = { ...raw, artist: esc(raw.artist), support: raw.support.map(esc), tagline: esc(raw.tagline),
      image: raw.image && esc(raw.image), url: raw.url && esc(raw.url), genres: raw.genres.map(esc) };
    const venue = venueById[s.venue];
    const start = new Date(s.start); // local NYC time, e.g. 2026-10-02T20:00
    const r = rng(`friends-${s.id}`);
    return {
      ...s,
      venue,
      start,
      vibes: vibesFor(s, venue, start.getHours()),
      description: s.tagline || '',
      friendsGoing: FRIENDS.filter(() => r() < 0.05).map(f => f.id), // sample friends
    };
  })
  .sort((a, b) => a.start - b.start);

// Genres come from the listings themselves (only some venues tag them so far).
const GENRES = [...new Set(SHOWS.flatMap(s => s.genres))].sort();

const UPDATED = RAW.updated ? new Date(RAW.updated) : null;
