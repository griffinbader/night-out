// Shindig — listings run in the browser; accounts & friends sync through Supabase (account.js).

// ---------- Saved state (your "going" / "interested" picks) ----------
// Signed out: picks live in this browser. Signed in: they come from your account.
function load(key, fallback) {
  try { const v = localStorage.getItem(key); return v ? JSON.parse(v) : fallback; } catch { return fallback; }
}
function save(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* storage unavailable — fine */ }
}

const going = new Set(load('no.going', []));
const interested = new Set(load('no.interested', []));
const persist = () => {
  if (Account.me.profile) return; // signed in: the account is the source of truth
  save('no.going', [...going]); save('no.interested', [...interested]);
};

const state = {
  tab: 'discover',
  when: null,      // null = every upcoming show; or a timeframe button, or 'range'
  from: null,      // 'YYYY-MM-DD' start of a picked date range
  to: null,        // 'YYYY-MM-DD' end of it (same as from for a single day)
  rangeOpen: false,
  calMonth: null,  // first day of the month the calendar shows, 'YYYY-MM-01'
  picking: false,  // true after the first tap: the next tap sets the end of the range
  limit: 80,       // cards drawn so far; more load as you scroll
  boroughs: new Set(),
  hoods: new Set(),
  genres: new Set(),
  vibes: new Set(),
  maxPrice: null,        // null = any price; 0 = free only
  view: 'list',          // 'list' | 'map'
  query: '',
  moreFilters: false,
};

const byId = Object.fromEntries(SHOWS.map(s => [s.id, s]));
const view = document.getElementById('view');
const sheet = document.getElementById('sheet');

// ---------- Dates ----------
const DAY = 86400000;
function midnight(d = new Date()) { const x = new Date(d); x.setHours(0, 0, 0, 0); return x; }
function addDays(d, n) { const x = new Date(d); x.setDate(x.getDate() + n); return x; }

function range(when) {
  const t = midnight();
  switch (when) {
    case 'tonight': return [t, addDays(t, 1)];
    case 'tomorrow': return [addDays(t, 1), addDays(t, 2)];
    case 'weekend': {
      const day = t.getDay(); // 0 Sun … 6 Sat
      const start = [5, 6, 0].includes(day) ? t : addDays(t, 5 - day);
      const untilMon = (8 - start.getDay()) % 7 || 7;
      return [start, addDays(start, untilMon)];
    }
    case 'week': return [t, addDays(t, 7)];
    case 'twoweeks': return [t, addDays(t, 14)];
    case 'range': return [new Date(state.from + 'T00:00'), addDays(new Date((state.to || state.from) + 'T00:00'), 1)];
    default: return [t, new Date(8.64e15)]; // no timeframe picked: everything from today on
  }
}

const fmtTime = d => { const h = d.getHours() % 12 || 12; return { h, ap: d.getHours() >= 12 ? 'PM' : 'AM' }; };
const fmtDate = d => d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
function dayLabel(d) {
  const diff = Math.round((midnight(d) - midnight()) / DAY);
  if (diff === 0) return 'Tonight';
  if (diff === 1) return 'Tomorrow';
  return d.toLocaleDateString('en-US', { weekday: 'long' });
}
const priceLabel = p => (p == null ? '' : p === 0 ? 'Free' : `$${p}`);

// ---------- Filtering ----------
function inWhen(s) { const [a, b] = range(state.when); return s.start >= a && s.start < b; }
function matches(s, skip = '') {
  if (!inWhen(s)) return false;
  if (skip !== 'borough' && state.boroughs.size && !state.boroughs.has(s.venue.borough)) return false;
  if (skip !== 'hood' && state.hoods.size && !state.hoods.has(s.venue.hood)) return false;
  if (skip !== 'genre' && state.genres.size && !s.genres.some(g => state.genres.has(g))) return false;
  if (skip !== 'vibe' && state.vibes.size && !s.vibes.some(v => state.vibes.has(v))) return false;
  if (state.maxPrice != null) {
    if (s.price != null && s.price > state.maxPrice) return false;  // base (pre-fee) prices; unknown prices go last
  }
  if (state.query) {
    const q = state.query.toLowerCase();
    const hay = [s.artist, ...s.support, s.venue.name, s.venue.hood].join(' ').toLowerCase();
    if (!hay.includes(q)) return false;
  }
  return true;
}
const countFor = (skip, test) => SHOWS.filter(s => matches(s, skip) && test(s)).length;
const activeFilterCount = () => state.boroughs.size + state.hoods.size + state.genres.size + state.vibes.size + (state.maxPrice != null) + !!state.query;

// ---------- Pieces ----------
// ---------- Friends' plans ----------
let friendGoing = {};   // show id -> [friend profile ids]
let snapshots = {};     // show id -> listing saved with a plan (for shows no longer listed)

function syncFromAccount() {
  const { me } = Account;
  friendGoing = {};
  snapshots = {};
  for (const p of [...me.friendPlans, ...me.myPlans]) {
    if (!byId[p.show_id] && p.show?.artist) snapshots[p.show_id] = fromSnapshot(p.show_id, p.show);
  }
  for (const p of me.friendPlans) {
    if (p.status === 'going') (friendGoing[p.show_id] ||= []).push(p.user_id);
  }
  if (me.profile) {
    going.clear(); interested.clear();
    for (const p of me.myPlans) (p.status === 'going' ? going : interested).add(p.show_id);
  }
}

function fromSnapshot(id, snap) {
  const venue = venueById[snap.venue] || { id: snap.venue, name: snap.venue, hood: '', borough: '', vibes: [], size: 'small' };
  return {
    id, artist: esc(snap.artist), support: (snap.support || []).map(esc), venue, start: new Date(snap.start),
    image: snap.image && esc(snap.image), genres: snap.genres || [], vibes: [], price: snap.price, url: snap.url && esc(snap.url),
    description: '', tagline: '',
  };
}

const showFor = id => byId[id] || snapshots[id];
const friendsAt = s => friendGoing[s.id] || [];
const avatar = (p, cls = '') => `<span class="face ${cls}" style="background:${p.color}">${esc(p.display_name)[0].toUpperCase()}</span>`;

function faces(ids, max = 3) {
  const people = ids.map(Account.profileById).filter(Boolean);
  if (!people.length) return '';
  const first = esc(people[0].display_name);
  const label = people.length === 1 ? `${first} is going` : `${first} + ${people.length - 1} going`;
  return `<div class="faces"><div class="face-stack">${people.slice(0, max).map(p => avatar(p)).join('')}</div>${label}</div>`;
}

function actionButtons(s) {
  if (s.start < midnight()) {
    return going.has(s.id) ? `<span class="went">✓ You went</span>` : '';
  }
  return `<div class="actions">
    <button class="btn interested ${interested.has(s.id) ? 'on' : ''}" data-act="interested" data-id="${s.id}">${interested.has(s.id) ? '★ Interested' : '☆ Interested'}</button>
    <button class="btn going ${going.has(s.id) ? 'on' : ''}" data-act="going" data-id="${s.id}">${going.has(s.id) ? '✓ Going' : 'Going'}</button>
  </div>`;
}

// Band photo. Sample artists have no photos, so we draw a little screen-print
// style poster from the name; once real listings arrive, s.image holds the photo URL.
const INKS = ['#ff4d2e', '#2f4bff', '#ffd23f', '#ff9ccf', '#22c07a', '#b8a2ff', '#ff9f1c', '#fffaf1', '#141210'];

function art(s) {
  // real photo sits on top of the generated poster; if it fails to load, the poster shows
  const photo = s.image ? `<img src="${s.image}" alt="${s.artist}" loading="lazy" onerror="this.remove()">` : '';
  const r = rng(`art-${s.artist}`);
  const take = () => { const c = pick(r, pool); pool.splice(pool.indexOf(c), 1); return c; };
  const pool = INKS.slice(0, -1); // keep black out of the background so records/outlines show
  const bg = take();
  pool.push('#141210');
  const a = take(), b = take();
  const k = '#141210';
  const n = (lo, hi) => Math.round(lo + r() * (hi - lo));
  const shapes = [
    // big sun + small moon
    () => `<circle cx="${n(35, 65)}" cy="${n(35, 60)}" r="${n(26, 34)}" fill="${a}"/><circle cx="${n(15, 85)}" cy="${n(15, 30)}" r="${n(7, 11)}" fill="${b}"/>`,
    // record
    () => `<circle cx="50" cy="50" r="38" fill="${k}"/>${[31, 25, 19].map(rr => `<circle cx="50" cy="50" r="${rr}" fill="none" stroke="${bg}" stroke-opacity=".35" stroke-width=".8"/>`).join('')}<circle cx="50" cy="50" r="12" fill="${a}"/><circle cx="50" cy="50" r="2" fill="${bg}"/>`,
    // stripes + half sun
    () => `${[0, 1, 2, 3, 4].map(i => `<rect y="${56 + i * 9}" width="100" height="4.5" fill="${a}"/>`).join('')}<path d="M18 56a32 32 0 0 1 64 0z" fill="${b}"/>`,
    // halftone dots + blob
    () => `${Array.from({ length: 36 }, (_, i) => `<circle cx="${9 + (i % 6) * 16.5}" cy="${9 + Math.floor(i / 6) * 16.5}" r="${2 + (i % 6) * 0.9}" fill="${a}"/>`).join('')}<circle cx="${n(30, 70)}" cy="${n(40, 70)}" r="${n(16, 22)}" fill="${b}" stroke="${k}" stroke-width="2"/>`,
    // tilted squares
    () => `<rect x="20" y="20" width="60" height="60" fill="${a}" transform="rotate(${n(-20, 20)} 50 50)"/><rect x="36" y="36" width="28" height="28" fill="${b}" stroke="${k}" stroke-width="2" transform="rotate(${n(20, 50)} 50 50)"/>`,
    // wavy lines
    () => [0, 1, 2, 3].map(i => `<path d="M-5 ${28 + i * 16} q 13 -12 26 0 t 26 0 t 26 0 t 26 0" fill="none" stroke="${i % 2 ? b : a}" stroke-width="6" stroke-linecap="round"/>`).join(''),
    // arch
    () => `<path d="M22 100V52a28 28 0 0 1 56 0v48z" fill="${a}"/><circle cx="50" cy="${n(46, 58)}" r="10" fill="${b}"/>`,
    // starburst
    () => `<polygon points="${Array.from({ length: 24 }, (_, i) => { const rr = i % 2 ? 18 : 40, t = (i / 24) * Math.PI * 2; return `${50 + rr * Math.cos(t)},${50 + rr * Math.sin(t)}`; }).join(' ')}" fill="${a}"/><circle cx="50" cy="50" r="10" fill="${b}"/>`,
  ];
  return `<svg viewBox="0 0 100 100" preserveAspectRatio="xMidYMid slice" aria-hidden="true"><rect width="100" height="100" fill="${bg}"/>${pick(r, shapes)()}</svg>${photo}`;
}

// Filled color for each selected chip, so filters feel like stickers.
const CHIP_COLORS = { borough: '#ffd23f', hood: '#ff9f1c', vibe: '#ff9ccf', genre: '#b8a2ff', price: '#22c07a' };

function card(s) {
  const t = fmtTime(s.start);
  return `<article class="card" data-open="${s.id}">
    <div class="thumb">
      ${art(s)}
      <div class="time">${t.h}${t.ap.toLowerCase()}</div>
    </div>
    <div>
      <div class="artist">${s.artist}</div>
      ${s.support.length ? `<div class="support">with ${s.support.join(', ')}</div>` : ''}
      <div class="where">${s.venue.name} <span class="boro">· ${s.venue.hood === s.venue.borough ? s.venue.borough : `${s.venue.hood}, ${s.venue.borough}`}</span></div>
      <div class="tags">
        ${s.genres.map(g => `<span class="tag genre">${g}</span>`).join('')}
        ${s.vibes.map(v => `<span class="tag">${v}</span>`).join('')}
      </div>
      <div class="card-foot">
        ${s.price != null ? `<span class="price ${s.price === 0 ? 'free' : ''}">${priceLabel(s.price)}</span>` : '<span></span>'}
        ${faces(friendsAt(s))}
        ${actionButtons(s)}
      </div>
    </div>
  </article>`;
}

function chipRow(label, items, selected, group, counter) {
  return `<div class="filter-group"><div class="filter-label">${label}</div><div class="chips">
    ${items.map(v => {
      const n = counter(v);
      const on = selected.has(v);
      return `<button class="chip ${on ? 'on' : ''}" style="--c:${CHIP_COLORS[group]}" data-chip="${group}" data-val="${v}" ${!n && !on ? 'disabled' : ''}>${v}<span class="n">${n}</span></button>`;
    }).join('')}
  </div></div>`;
}

// ---------- Discover ----------
const WHENS = [['tonight', 'Tonight'], ['tomorrow', 'Tomorrow'], ['weekend', 'This weekend'], ['week', 'Next 7 days']];

// "Pick a date": a chip with the phone's native date picker laid over it.
const isoDay = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
const shortDay = iso => new Date(iso + 'T00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
function rangeLabel() {
  if (!state.from) return '';
  if (!state.to || state.to === state.from) return new Date(state.from + 'T00:00').toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
  const [a, b] = [shortDay(state.from), shortDay(state.to)];
  return a.split(' ')[0] === b.split(' ')[0] ? `${a} to ${b.split(' ')[1]}` : `${a} to ${b}`;
}

// 📅 opens a from/to picker. Pick one day or a stretch of days.
function datePicker() {
  const on = state.when === 'range' && state.from;
  return `<button class="date-chip ${on ? 'on' : ''}" data-range-toggle aria-expanded="${state.rangeOpen}" title="Pick dates">📅${on ? ' ' + rangeLabel() : ''}</button>`;
}

// Dropdown calendar: tap a day for that night, tap a second day to make it a range.
function rangePanel() {
  if (!state.rangeOpen) return '';
  const today = isoDay(new Date());
  const last = SHOWS.length ? isoDay(SHOWS[SHOWS.length - 1].start) : today;
  const month = new Date((state.calMonth || (state.from || today).slice(0, 7) + '-01') + 'T00:00');
  const first = new Date(month), lead = first.getDay();
  const days = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
  const withShows = new Set(SHOWS.map(s => isoDay(s.start)));
  const from = state.when === 'range' ? state.from : null, to = state.when === 'range' ? (state.to || state.from) : null;
  let cells = '<span></span>'.repeat(lead);
  for (let d = 1; d <= days; d++) {
    const iso = isoDay(new Date(month.getFullYear(), month.getMonth(), d));
    const off = iso < today || iso > last;
    const cls = [
      from && iso >= from && iso <= to ? 'in' : '', iso === from ? 'start' : '', iso === to ? 'end' : '',
      iso === today ? 'today' : '', withShows.has(iso) ? 'has' : '',
    ].join(' ');
    cells += `<button class="cal-day ${cls}" data-cal-day="${iso}" ${off ? 'disabled' : ''}>${d}</button>`;
  }
  const monthIso = d => isoDay(d).slice(0, 8) + '01';
  const prev = monthIso(new Date(month.getFullYear(), month.getMonth() - 1, 1));
  const next = monthIso(new Date(month.getFullYear(), month.getMonth() + 1, 1));
  return `<div class="cal">
    <div class="cal-head">
      <button class="cal-nav" data-cal-month="${prev}" ${prev < today.slice(0, 8) + '01' ? 'disabled' : ''} aria-label="Previous month">‹</button>
      <b>${month.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })}</b>
      <button class="cal-nav" data-cal-month="${next}" ${next > last ? 'disabled' : ''} aria-label="Next month">›</button>
    </div>
    <div class="cal-grid">${['S', 'M', 'T', 'W', 'T', 'F', 'S'].map(x => `<span class="cal-dow">${x}</span>`).join('')}${cells}</div>
    <div class="cal-foot">
      <span>${state.picking ? 'Tap another day to make it a range' : 'Tap a day, or two days for a range'}</span>
      <span>${state.when === 'range' ? '<button class="btn" data-range-clear>Clear</button>' : ''}<button class="btn cal-done" data-range-toggle>Done</button></span>
    </div>
  </div>`;
}

// First visit: a quick note on what this is. Hidden once dismissed or signed in.
function welcomeCard() {
  if (load('no.welcomed', false) || Account.me.profile) return '';
  return `<div class="welcome">
    <p>Shindig compiles every concert happening in NYC. Pick a night, filter by borough, genre, vibe, or price, and tap any show for tickets.</p>
    <p>Sign in to see where your friends are headed and mark where you are too.</p>
    <div class="welcome-actions">${Account.enabled ? '<button class="btn welcome-signin" data-welcome="signin">Sign in</button>' : ''}<button class="btn" data-welcome="ok">Got it</button></div>
  </div>`;
}

function renderDiscover() {
  view.innerHTML = `
    ${welcomeCard()}
    <h2>Where's the <em>music</em>?</h2>
    <div class="when">${datePicker()}${WHENS.map(([k, l]) => `<button data-when="${k}" class="${state.when === k ? 'on' : ''}">${l}</button>`).join('')}</div>
    ${rangePanel()}
    <div id="controls"></div>
    <div id="list"></div>`;
  renderControls();
  renderList();
}

// Price slider: 0 = free only, far right = any price.
const PRICE_MAX = 150;
const pricePct = () => Math.round(((state.maxPrice ?? PRICE_MAX) / PRICE_MAX) * 100);
const priceText = () => state.maxPrice == null ? 'Any price' : state.maxPrice === 0 ? 'Free only' : `Up to $${state.maxPrice}`;

function renderControls() {
  const hoods = [...new Set(VENUES.filter(v => state.boroughs.has(v.borough)).map(v => v.hood))].filter(h => !BOROUGHS.includes(h)).sort();
  const priceOn = state.maxPrice != null;
  document.getElementById('controls').innerHTML = `
    ${chipRow('Borough', BOROUGHS, state.boroughs, 'borough', b => countFor('borough', s => s.venue.borough === b))}
    ${hoods.length ? chipRow('Neighborhood', hoods, state.hoods, 'hood', h => countFor('hood', s => s.venue.hood === h)) : ''}
    ${chipRow('Genre', GENRES, state.genres, 'genre', g => countFor('genre', s => s.genres.includes(g)))}
    ${chipRow('Vibe', VIBES, state.vibes, 'vibe', v => countFor('vibe', s => s.vibes.includes(v)))}
    <button class="filter-toggle" data-more>${state.moreFilters ? '− Fewer filters' : `+ Price${priceOn ? ` (${priceText()})` : ''}`}</button>
    ${state.moreFilters ? `
      <div class="filter-group price-group">
        <div class="filter-label">Price</div>
        <div class="price-slider" id="price-slider" style="--pct:${pricePct()}">
          <output class="price-bubble" id="price-text" for="price-range">${priceText()}</output>
          <span class="price-pointer" aria-hidden="true"></span>
          <input type="range" id="price-range" min="0" max="${PRICE_MAX}" step="5" value="${state.maxPrice ?? PRICE_MAX}" aria-label="Maximum price">
          <div class="price-ticks"><span>Free</span><span>$50</span><span>$100</span><span>Any</span></div>
        </div>
      </div>` : ''}
    <input class="search" id="search" type="search" placeholder="Search artist or venue" value="${state.query}">`;
}

const MISSING_CTA = `<div class="missing-cta">Know about a show that isn't here? <button data-missing>Tell us</button></div>`;

// Long lists draw in pages as you scroll, so opening every show stays quick on a phone.
let listKey = '', moreObserver = null;
function watchForMore(total) {
  moreObserver?.disconnect();
  const el = document.getElementById('load-more');
  if (!el || !('IntersectionObserver' in window)) return;
  moreObserver = new IntersectionObserver(entries => {
    if (!entries[0].isIntersecting || state.limit >= total) return;
    state.limit += 120;
    renderList();
  }, { rootMargin: '1200px 0px' });
  moreObserver.observe(el);
}

function renderList() {
  const list = SHOWS.filter(s => matches(s));
  const key = JSON.stringify([state.when, state.from, state.to, [...state.boroughs], [...state.hoods], [...state.genres], [...state.vibes], state.maxPrice, state.query]);
  if (key !== listKey) { listKey = key; state.limit = 80; }
  const more = total => total > state.limit
    ? `<button id="load-more" class="load-more" data-load-more>Show more (${total - state.limit} left)</button>` : '';
  const el = document.getElementById('list');
  const head = `<div class="result-count"><span>${list.length} show${list.length === 1 ? '' : 's'}</span>
    <span class="result-actions">${activeFilterCount() ? '<button data-clear>Clear filters</button>' : ''}
    <span class="view-toggle"><button data-view="list" class="${state.view === 'list' ? 'on' : ''}">List</button><button data-view="map" class="${state.view === 'map' ? 'on' : ''}">Map</button></span></span></div>`;
  if (state.view === 'map') { el.innerHTML = head + '<div id="map"></div>'; return drawMap(list); }
  if (!list.length) {
    el.innerHTML = head + `<div class="empty"><b>Nothing matches</b>Try a wider timeframe or fewer filters.</div>` + MISSING_CTA;
    return;
  }
  const byDay = shows => {
    let out = '', lastDay = '';
    for (const s of shows) {
      const k = midnight(s.start).getTime();
      if (k !== lastDay) { out += `<div class="day"><span class="day-name">${dayLabel(s.start)}</span><span class="day-date">${s.start.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</span></div>`; lastDay = k; }
      out += card(s);
    }
    return out;
  };
  if (state.maxPrice == null) {
    el.innerHTML = head + byDay(list.slice(0, state.limit)) + (more(list.length) || MISSING_CTA);
    return watchForMore(list.length);
  }
  // Price filter on: shows with a known base price first, then the rest under their own heading
  const ordered = [...list.filter(s => s.price != null), ...list.filter(s => s.price == null)];
  const page = ordered.slice(0, state.limit);
  const priced = page.filter(s => s.price != null), unpriced = page.filter(s => s.price == null);
  const unpricedTotal = list.length - list.filter(s => s.price != null).length;
  el.innerHTML = head
    + (priced.length ? byDay(priced) : `<div class="empty"><b>No listed prices in range</b>Shows without a listed price are below.</div>`)
    + (unpriced.length ? `<div class="price-divider"><b>Price not listed</b><span>${unpricedTotal} show${unpricedTotal === 1 ? '' : 's'} · check the ticket link</span></div>${byDay(unpriced)}` : '')
    + (more(ordered.length) || MISSING_CTA);
  watchForMore(ordered.length);
}

// ---------- Map ----------
// One pin per venue, showing how many of the currently filtered shows are there.
let map = null;
function drawMap(list) {
  if (map) { map.remove(); map = null; }
  if (!window.L) { document.getElementById('map').innerHTML = '<div class="empty">Map couldn’t load. Check your connection.</div>'; return; }
  const byVenue = {};
  for (const s of list) if (s.venue.lat) (byVenue[s.venue.id] ||= { venue: s.venue, shows: [] }).shows.push(s);
  map = L.map('map', { zoomControl: true, attributionControl: true }).setView([40.715, -73.96], 12);
  // Free OpenStreetMap tiles, darkened with CSS (.leaflet-tile-pane) to fit the site.
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  }).addTo(map);
  const pins = Object.values(byVenue).map(({ venue, shows }) => {
    const icon = L.divIcon({ className: 'pin', html: `<span>${shows.length}</span>`, iconSize: [34, 34], iconAnchor: [17, 17] });
    const rows = shows.slice(0, 8).map(s => `<a data-open="${s.id}"><b>${s.artist}</b><span>${dayLabel(s.start) === 'Tonight' ? 'Tonight' : fmtDate(s.start)} · ${fmtTime(s.start).h}${fmtTime(s.start).ap.toLowerCase()}</span></a>`).join('');
    const more = shows.length > 8 ? `<div class="pop-more">+ ${shows.length - 8} more</div>` : '';
    return L.marker([venue.lat, venue.lng], { icon })
      .bindPopup(`<div class="pop"><div class="pop-venue">${venue.name}</div><div class="pop-hood">${venue.hood}, ${venue.borough}</div>${rows}${more}</div>`, { maxWidth: 240, autoPanPadding: [24, 24] })
      .addTo(map);
  });
  if (pins.length) map.fitBounds(L.featureGroup(pins).getBounds().pad(0.15), { maxZoom: 14 });
  else document.getElementById('map').insertAdjacentHTML('afterbegin', '<div class="map-empty">No shows match. Try a wider timeframe.</div>');
}

// ---------- Friends ----------
function renderFriends() {
  const { me } = Account;
  if (!me.profile) {
    view.innerHTML = `<h2>The <em>crew</em></h2>
      ${invitePending ? '<div class="invite-note">You’ve been invited! Sign in and you’ll be connected automatically.</div>' : ''}
      ${accountPanel(invitePending ? 'Your friend is waiting on the other side.' : 'See where your friends are going. Sign in to add them.')}`;
    return;
  }
  const now = midnight();
  const item = (p, past) => {
    const s = showFor(p.show_id);
    const f = Account.profileById(p.user_id);
    if (!s || !f) return '';
    return `<div class="feed-item" data-open="${s.id}">
      ${avatar(f, 'lg')}
      <div><p><b>${esc(f.display_name)}</b> ${past ? 'went to' : 'is going to'} <b>${s.artist}</b></p>
      <p class="meta">${s.venue.name} · ${dayLabel(s.start) === 'Tonight' ? 'Tonight' : fmtDate(s.start)}</p></div>
    </div>`;
  };
  const going = me.friendPlans.filter(p => p.status === 'going' && p.show_start);
  const upcoming = going.filter(p => new Date(p.show_start) >= now).sort((a, b) => new Date(a.show_start) - new Date(b.show_start));
  const recent = going.filter(p => new Date(p.show_start) < now).sort((a, b) => new Date(b.show_start) - new Date(a.show_start)).slice(0, 15);
  const person = (p, action) => `<div class="person">${avatar(p, 'lg')}<div><b>${esc(p.display_name)}</b><span>@${p.username}</span></div>${action}</div>`;

  view.innerHTML = `
    <h2>The <em>crew</em></h2>
    <button class="btn primary invite-btn" data-invite>Invite friends</button>
    <form class="add-friend" data-form="find">
      <input class="search" name="username" placeholder="Add a friend by @username" autocomplete="off" autocapitalize="none" required>
      <button class="btn primary" type="submit">Add</button>
    </form>
    <div id="find-result" class="form-msg"></div>
    ${me.incoming.length ? `<h3>Want to be friends</h3>${me.incoming.map(p => person(p, `<button class="btn going on" data-add="${p.id}">Add back</button>`)).join('')}` : ''}
    ${me.friends.length ? `<div class="friend-row">${me.friends.map(f => `<div>${avatar(f, 'lg')}${esc(f.display_name)}</div>`).join('')}</div>` : ''}
    ${me.outgoing.length ? `<h3>Waiting on</h3>${me.outgoing.map(p => person(p, `<button class="btn" data-unadd="${p.id}">Cancel</button>`)).join('')}` : ''}
    <h3>Going soon</h3>
    ${upcoming.length ? upcoming.map(p => item(p, false)).join('') : `<div class="empty">${me.friends.length ? 'No plans from friends yet.' : 'Add friends to see where they’re headed.'}</div>`}
    ${recent.length ? `<h3>Recently went</h3>${recent.map(p => item(p, true)).join('')}` : ''}
    ${me.friends.length ? `<h3>Friends</h3>${me.friends.map(p => person(p, `<button class="btn" data-unadd="${p.id}">Remove</button>`)).join('')}` : ''}`;
}

// ---------- Account panel (sign in / pick a username / signed-in bar) ----------
const COLORS = ['#ffd23f', '#ff9ccf', '#22c07a', '#b8a2ff', '#6f86ff', '#ff9f1c', '#ff4d2e'];

function accountPanel(pitch) {
  const { me } = Account;
  if (!Account.enabled) return '';
  if (!me.ready) return '<div class="empty">Loading…</div>';
  if (!me.user) {
    return `<form class="account-card" data-form="signin">
      <b>Sign in to Shindig</b>
      <p>${pitch} No password needed, we'll email you a sign-in link.</p>
      <input class="search" type="email" name="email" placeholder="you@email.com" autocomplete="email" required>
      <button class="btn primary" type="submit">Email me a link</button>
      <div class="form-msg" id="signin-msg"></div>
    </form>`;
  }
  if (!me.profile) {
    return `<form class="account-card" data-form="profile">
      <b>Pick your name</b>
      <p>Friends find you by your username.</p>
      <input class="search" name="display" placeholder="Your name" maxlength="40" required>
      <input class="search" name="username" placeholder="username (letters, numbers, _)" pattern="[a-z0-9_]{3,20}" maxlength="20" autocapitalize="none" required>
      <div class="swatches">${COLORS.map((c, i) => `<label><input type="radio" name="color" value="${c}" ${i ? '' : 'checked'}><span style="background:${c}"></span></label>`).join('')}</div>
      <button class="btn primary" type="submit">Let's go</button>
      <div class="form-msg" id="profile-msg"></div>
    </form>`;
  }
  return `<div class="account-bar">${avatar(me.profile, 'lg')}<div><b>${esc(me.profile.display_name)}</b><span>@${me.profile.username}</span></div>
    <button class="btn" data-signout>Sign out</button></div>`;
}

function accountFooter() {
  return Account.me.profile ? '<p class="danger-zone"><button data-delete-account>Delete my account</button></p>' : '';
}

// ---------- My Shows ----------
function topOf(arr) {
  const c = {};
  arr.forEach(x => (c[x] = (c[x] || 0) + 1));
  return Object.entries(c).sort((a, b) => b[1] - a[1])[0]?.[0] || 'None yet';
}

function renderMine() {
  const now = midnight();
  const mine = [...going].map(showFor).filter(Boolean);
  const history = mine.filter(s => s.start < now).sort((a, b) => b.start - a.start);
  const upcoming = mine.filter(s => s.start >= now).sort((a, b) => a.start - b.start);
  const maybe = [...interested].map(showFor).filter(s => s && s.start >= now && !going.has(s.id)).sort((a, b) => a.start - b.start);
  const thisYear = history.filter(s => s.start.getFullYear() === now.getFullYear());

  view.innerHTML = `
    <h2>Your <em>nights</em></h2>
    ${accountPanel('Save your plans and show history to your account, on every device.')}
    <div class="stats">
      <div class="stat"><b>${thisYear.length}</b><span>shows this year</span></div>
      <div class="stat"><b>${new Set(history.map(s => s.venue.id)).size}</b><span>venues</span></div>
      <div class="stat text"><b>${topOf(history.map(s => s.venue.name))}</b><span>your spot</span></div>
      <div class="stat text"><b>${topOf(history.flatMap(s => s.genres))}</b><span>top genre</span></div>
    </div>
    <h3>Going</h3>
    ${upcoming.length ? upcoming.map(card).join('') : '<div class="empty"><b>No plans yet</b>Tap “Going” on a show in Discover.</div>'}
    ${maybe.length ? `<h3>Interested</h3>${maybe.map(card).join('')}` : ''}
    <h3>History</h3>
    ${history.length ? '' : '<div class="empty"><b>Nothing yet</b>Shows you mark “Going” land here after the night.</div>'}
    ${history.map(s => `<div class="history-item" data-open="${s.id}">
      <div><div class="a">${s.artist}</div><div class="v">${s.venue.name}</div></div>
      <div class="d">${s.start.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</div>
    </div>`).join('')}
    ${accountFooter()}`;
}

// ---------- Sharing, invites & calendar ----------
const BASE_URL = location.origin + location.pathname;
const showLink = s => `${BASE_URL}#show=${encodeURIComponent(s.id)}`;
const plain = h => { const d = document.createElement('div'); d.innerHTML = h; return d.textContent; };

function toast(msg) {
  let el = document.getElementById('toast');
  if (!el) { el = document.createElement('div'); el.id = 'toast'; document.body.appendChild(el); }
  el.textContent = msg;
  el.classList.add('on');
  clearTimeout(toast.t);
  toast.t = setTimeout(() => el.classList.remove('on'), 2600);
}

// Phone share sheet when available, otherwise copy the link.
async function shareLink({ title, text, url }) {
  if (navigator.share) {
    try { await navigator.share({ title, text, url }); return; } catch (e) { if (e.name === 'AbortError') return; }
  }
  try { await navigator.clipboard.writeText(url); toast('Link copied'); }
  catch { prompt('Copy this link:', url); }
}

function shareShow(s) {
  const when = `${dayLabel(s.start) === 'Tonight' ? 'tonight' : fmtDate(s.start)}`;
  shareLink({ title: `${plain(s.artist)} · Shindig`, text: `${plain(s.artist)} at ${s.venue.name}, ${when}`, url: showLink(s) });
}

// Calendar: .ics file (Apple Calendar / Outlook) or a Google Calendar link. Shows default to 3 hours.
const calStamp = d => `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}T${String(d.getHours()).padStart(2, '0')}${String(d.getMinutes()).padStart(2, '0')}00`;
const icsText = v => String(v).replace(/[\;,]/g, m => '\\' + m).replace(/\n/g, '\\n');

function calendarDetails(s) {
  const end = new Date(s.start.getTime() + 3 * 3600e3);
  const where = [s.venue.name, s.venue.hood, s.venue.borough, 'NY'].filter((x, i, a) => x && a.indexOf(x) === i).join(', ');
  const lineup = [plain(s.artist), ...s.support.map(plain)].join(', ');
  return { title: `${plain(s.artist)} at ${s.venue.name}`, where, start: calStamp(s.start), end: calStamp(end),
    details: `${lineup}\n${s.url ? 'Tickets: ' + plain(s.url) + '\n' : ''}On Shindig: ${showLink(s)}` };
}

function downloadIcs(s) {
  const c = calendarDetails(s);
  const ics = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Shindig//EN', 'BEGIN:VEVENT',
    `UID:${s.id}@shindig`, `DTSTAMP:${new Date().toISOString().replace(/[-:]/g, '').slice(0, 15)}Z`,
    `DTSTART;TZID=America/New_York:${c.start}`, `DTEND;TZID=America/New_York:${c.end}`,
    `SUMMARY:${icsText(c.title)}`, `LOCATION:${icsText(c.where)}`, `DESCRIPTION:${icsText(c.details)}`,
    `URL:${showLink(s)}`, 'END:VEVENT', 'END:VCALENDAR'].join('\r\n');
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([ics], { type: 'text/calendar' }));
  a.download = `${plain(s.artist).replace(/[^\w]+/g, '-').slice(0, 40)}.ics`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 5000);
}

function googleCalUrl(s) {
  const c = calendarDetails(s);
  return 'https://calendar.google.com/calendar/render?' + new URLSearchParams({
    action: 'TEMPLATE', text: c.title, dates: `${c.start}/${c.end}`, ctz: 'America/New_York', location: c.where, details: c.details,
  });
}

// Links like #show=<id> (open a show) and #invite=<code> (become friends).
async function handleLink() {
  const params = new URLSearchParams(location.hash.slice(1));
  if (params.get('invite')) {
    try { localStorage.setItem('no.invite', params.get('invite')); } catch { /* fine */ }
    history.replaceState(null, '', BASE_URL);
    await tryPendingInvite();
  }
  if (params.get('show')) {
    const id = params.get('show');
    history.replaceState(null, '', BASE_URL);
    if (showFor(id)) openSheet(id); else toast('That show isn’t listed anymore.');
  }
}

let invitePending = null;
async function tryPendingInvite() {
  let code = null;
  try { code = localStorage.getItem('no.invite'); } catch { /* fine */ }
  invitePending = code;
  if (!code || !Account.me.ready) return render();
  if (!Account.me.profile) { state.tab = 'friends'; return render(); } // sign in first, then we connect
  try {
    const who = await Account.acceptInvite(code);
    try { localStorage.removeItem('no.invite'); } catch { /* fine */ }
    invitePending = null;
    state.tab = 'friends';
    render();
    toast(who?.self ? 'That’s your own invite link!' : `You and ${who.display_name} are now friends`);
  } catch (err) {
    try { localStorage.removeItem('no.invite'); } catch { /* fine */ }
    invitePending = null;
    toast(err.message);
  }
}

// ---------- Detail sheet ----------
function openSheet(id) {
  const s = showFor(id);
  if (!s) return;
  const t = fmtTime(s.start);
  sheet.innerHTML = `<div class="sheet-body">
    <div class="hero">
      ${art(s)}
      <button class="sheet-close" data-close aria-label="Close">✕</button>
    </div>
    <div class="when-line">${dayLabel(s.start)} · ${fmtDate(s.start)} · ${t.h} ${t.ap}</div>
    <div class="artist">${s.artist}</div>
    <div class="where">${s.venue.name} · ${s.venue.hood === s.venue.borough ? s.venue.borough : `${s.venue.hood}, ${s.venue.borough}`}</div>
    <div class="tags">${s.genres.map(g => `<span class="tag genre">${g}</span>`).join('')}${s.vibes.map(v => `<span class="tag">${v}</span>`).join('')}</div>
    ${s.description ? `<p class="desc">${s.description}</p>` : ''}
    <ul class="lineup">${[s.artist, ...s.support].map(a => `<li>${a}</li>`).join('')}</ul>
    ${s.price != null ? `<span class="price ${s.price === 0 ? 'free' : ''}">${s.price === 0 ? 'Free show' : `From $${s.price}`}</span>` : ''}
    ${friendsAt(s).length ? `<p>${faces(friendsAt(s), 6)}</p>` : ''}
    ${actionButtons(s)}
    ${s.url ? `<a class="ticket-link" href="${s.url}" target="_blank" rel="noopener">Tickets &amp; info ↗</a>` : ''}
    <div class="sheet-tools">
      <button class="btn" data-share="${s.id}">Send to a friend</button>
      ${s.start >= midnight() ? `<button class="btn" data-ics="${s.id}">+ Apple / Outlook</button>
      <a class="btn" href="${googleCalUrl(s)}" target="_blank" rel="noopener">+ Google Calendar</a>` : ''}
    </div>
    <p class="note">Shindig doesn't sell tickets. This opens the venue's own ticket page.</p>
    <div id="report-box"><button class="text-link" data-report-open="${s.id}">Something wrong with this listing?</button></div>
  </div>`;
  sheet.classList.remove('hidden');
}
const closeSheet = () => sheet.classList.add('hidden');

// ---------- Reports: wrong info on a show, or a show we're missing ----------
function openReport(id) {
  document.getElementById('report-box').innerHTML = `<form class="report-form" data-form="report" data-show="${esc(id)}">
    <div class="filter-label">What's wrong?</div>
    <label><input type="radio" name="kind" value="wrong_info" required> Wrong date, time, venue or lineup</label>
    <label><input type="radio" name="kind" value="not_artist"> Not an artist show</label>
    <label><input type="radio" name="kind" value="cancelled"> Cancelled</label>
    <label><input type="radio" name="kind" value="other"> Something else</label>
    <textarea name="details" maxlength="1000" rows="2" placeholder="Anything else? (optional)"></textarea>
    <div class="report-actions"><button type="submit" class="btn">Send</button><span id="report-msg" class="form-msg"></span></div>
  </form>`;
}

function openMissing() {
  sheet.innerHTML = `<div class="sheet-body missing-sheet">
    <button class="sheet-close" data-close aria-label="Close">✕</button>
    <h3>Missing a show?</h3>
    <p>Tell us the artist, venue and date, and we'll figure out why it didn't come through.</p>
    <form class="report-form" data-form="missing">
      <textarea name="details" maxlength="1000" rows="4" required placeholder="e.g. Geese at Forest Hills Stadium, Sat Oct 3"></textarea>
      <div class="report-actions"><button type="submit" class="btn">Send</button><span id="missing-msg" class="form-msg"></span></div>
    </form>
  </div>`;
  sheet.classList.remove('hidden');
}

// ---------- Rendering & events ----------
function render() {
  document.querySelectorAll('.tabs button').forEach(b => b.classList.toggle('active', b.dataset.tab === state.tab));
  ({ discover: renderDiscover, friends: renderFriends, mine: renderMine })[state.tab]();
}

function toggle(set, v) { set.has(v) ? set.delete(v) : set.add(v); }

document.addEventListener('click', e => {
  const t = e.target.closest('button, [data-open]');
  if (!t) { if (e.target === sheet) closeSheet(); return; }

  if (t.dataset.tab) { state.tab = t.dataset.tab; window.scrollTo(0, 0); return render(); }
  if (t.dataset.act) {
    e.stopPropagation();
    const id = t.dataset.id;
    if (t.dataset.act === 'going') { toggle(going, id); if (going.has(id)) interested.delete(id); }
    else { toggle(interested, id); if (interested.has(id)) going.delete(id); }
    persist();
    if (Account.me.profile) {
      const status = going.has(id) ? 'going' : interested.has(id) ? 'interested' : null;
      Account.setPlan(showFor(id), status);
    }
    const sheetOpen = !sheet.classList.contains('hidden');
    render();
    if (sheetOpen) openSheet(id);
    return;
  }
  if (t.dataset.close !== undefined) return closeSheet();
  if (t.dataset.reportOpen) return openReport(t.dataset.reportOpen);
  if (t.dataset.missing !== undefined) return openMissing();
  if (t.dataset.welcome) {
    save('no.welcomed', true);
    if (t.dataset.welcome === 'signin') { state.tab = 'mine'; window.scrollTo(0, 0); }
    return render();
  }
  if (t.dataset.signout !== undefined) return Account.signOut();
  if (t.dataset.deleteAccount !== undefined) {
    const ok = confirm('Delete your Shindig account? This permanently removes your profile, plans, show history and friends. It can’t be undone.');
    if (ok) Account.deleteAccount().then(() => toast('Your account was deleted.')).catch(err => toast(err.message));
    return;
  }
  if (t.dataset.share) return shareShow(showFor(t.dataset.share));
  if (t.dataset.ics) return downloadIcs(showFor(t.dataset.ics));
  if (t.dataset.invite !== undefined) {
    return Account.inviteLink()
      .then(url => shareLink({ title: 'Come to shows with me on Shindig', text: `${plain(Account.me.profile.display_name)} invited you to Shindig. See where they’re going and find shows in NYC.`, url }))
      .catch(err => toast(err.message));
  }
  if (t.dataset.add) return Account.addFriend(t.dataset.add);
  if (t.dataset.unadd) return Account.removeFriend(t.dataset.unadd);
  if (t.dataset.open) return openSheet(t.dataset.open);
  if (t.dataset.when) { // tap again to go back to every show
    state.when = state.when === t.dataset.when ? null : t.dataset.when;
    state.rangeOpen = false; state.limit = 80;
    return renderDiscover();
  }
  if (t.dataset.rangeToggle !== undefined) { state.rangeOpen = !state.rangeOpen; state.picking = false; return renderDiscover(); }
  if (t.dataset.calMonth) { state.calMonth = t.dataset.calMonth; return renderDiscover(); }
  if (t.dataset.calDay) {
    const day = t.dataset.calDay;
    if (state.picking && state.when === 'range' && day !== state.from) {
      [state.from, state.to] = day < state.from ? [day, state.from] : [state.from, day];
      state.picking = false; state.rangeOpen = false; // range picked: close
    } else {
      state.from = state.to = day; state.picking = true; // one night so far; a second tap extends it
    }
    state.when = 'range'; state.calMonth = day.slice(0, 8) + '01'; state.limit = 80;
    return renderDiscover();
  }
  if (t.dataset.rangeClear !== undefined) {
    state.when = null; state.from = state.to = null; state.picking = false; state.limit = 80;
    return renderDiscover();
  }
  if (t.dataset.chip) {
    const set = { borough: state.boroughs, hood: state.hoods, genre: state.genres, vibe: state.vibes }[t.dataset.chip];
    toggle(set, t.dataset.val);
    if (t.dataset.chip === 'borough') {
      // drop neighborhoods that no longer belong to a selected borough
      for (const h of [...state.hoods]) if (!VENUES.some(v => v.hood === h && state.boroughs.has(v.borough))) state.hoods.delete(h);
    }
    renderControls(); return renderList();
  }
  if (t.dataset.view) { state.view = t.dataset.view; return renderList(); }
  if (t.dataset.loadMore !== undefined) { state.limit += 120; return renderList(); }
  if (t.dataset.more !== undefined) { state.moreFilters = !state.moreFilters; return renderControls(); }
  if (t.dataset.clear !== undefined) {
    state.boroughs.clear(); state.hoods.clear(); state.genres.clear(); state.vibes.clear(); state.maxPrice = null; state.query = '';
    renderControls(); return renderList();
  }
});

document.addEventListener('submit', async e => {
  const form = e.target.closest('[data-form]');
  if (!form) return;
  e.preventDefault();
  const f = new FormData(form);
  const msg = (id, text) => { const el = document.getElementById(id); if (el) el.textContent = text; };
  const button = form.querySelector('button[type=submit]');
  if (button) button.disabled = true;
  try {
    if (form.dataset.form === 'signin') {
      await Account.sendLink(f.get('email').trim());
      msg('signin-msg', 'Check your email for the sign-in link.');
    } else if (form.dataset.form === 'profile') {
      await Account.createProfile(f.get('username').trim().toLowerCase(), f.get('display').trim(), f.get('color'));
    } else if (form.dataset.form === 'report') {
      const s = showFor(form.dataset.show);
      await Account.report({ kind: f.get('kind'), showId: form.dataset.show, details: f.get('details').trim(),
        showLabel: s ? `${plain(s.artist)} · ${s.venue.name} · ${fmtDate(s.start)}` : null });
      document.getElementById('report-box').innerHTML = '<p class="note">Thanks, we got it. We’ll take a look.</p>';
    } else if (form.dataset.form === 'missing') {
      await Account.report({ kind: 'missing', details: f.get('details').trim() });
      closeSheet();
      toast('Thanks, we got it. We’ll look into it.');
    } else if (form.dataset.form === 'find') {
      const name = f.get('username').trim();
      const person = await Account.findUser(name);
      if (!person) msg('find-result', `No one called @${name.replace(/^@/, '')} yet.`);
      else if (person.id === Account.me.profile.id) msg('find-result', 'That’s you!');
      else { await Account.addFriend(person.id); }
    }
  } catch (err) {
    msg({ signin: 'signin-msg', profile: 'profile-msg', find: 'find-result', report: 'report-msg', missing: 'missing-msg' }[form.dataset.form], err.message || 'Something went wrong.');
  } finally {
    if (button?.isConnected) button.disabled = false;
  }
});

document.addEventListener('change', e => {
  if (e.target.id === 'price-range') { renderControls(); renderList(); return; }
});

document.addEventListener('input', e => {
  if (e.target.id === 'search') { state.query = e.target.value.trim(); renderList(); }
  if (e.target.id === 'price-range') {
    const v = +e.target.value;
    state.maxPrice = v >= PRICE_MAX ? null : v;
    document.getElementById('price-text').textContent = priceText();
    document.getElementById('price-slider').style.setProperty('--pct', pricePct());
    renderList();
  }
});
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeSheet(); });


// When the account changes (sign in/out, friends, plans): bring over picks made
// while signed out, then redraw with account data.
Account.onChange(async () => {
  const { me } = Account;
  if (me.profile) {
    const local = [...load('no.going', []).map(id => ['going', id]), ...load('no.interested', []).map(id => ['interested', id])]
      .filter(([, id]) => byId[id] && !me.myPlans.some(p => p.show_id === id))
      .map(([status, id]) => ({ status, show: byId[id] }));
    save('no.going', []); save('no.interested', []);
    if (local.length) return Account.importPlans(local); // fires onChange again
  } else if (me.ready) {
    going.clear(); interested.clear();
    load('no.going', []).forEach(id => going.add(id));
    load('no.interested', []).forEach(id => interested.add(id));
  }
  syncFromAccount();
  if (me.profile && invitePending) return tryPendingInvite();
  const sheetId = !sheet.classList.contains('hidden') && sheet.querySelector('[data-id]')?.dataset.id;
  render();
  if (sheetId) openSheet(sheetId);
});

// Personal links for the test group look like ...?r=alex. Remember the first one this browser arrived with.
const refParam = new URLSearchParams(location.search).get('r');
if (refParam) {
  if (!load('no.ref', null)) save('no.ref', refParam.slice(0, 64));
  history.replaceState(null, '', location.pathname + location.hash);
}

render();
Account.init().then(() => { Account.logVisit(load('no.ref', null)); handleLink(); });
window.addEventListener('hashchange', handleLink);
