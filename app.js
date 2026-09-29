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
  when: 'weekend',
  boroughs: new Set(),
  hoods: new Set(),
  genres: new Set(),
  vibes: new Set(),
  price: 'any',
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
  if (state.price === 'free' && s.price !== 0) return false;
  if (state.price === 'u20' && s.price > 20) return false;
  if (state.query) {
    const q = state.query.toLowerCase();
    const hay = [s.artist, ...s.support, s.venue.name, s.venue.hood].join(' ').toLowerCase();
    if (!hay.includes(q)) return false;
  }
  return true;
}
const countFor = (skip, test) => SHOWS.filter(s => matches(s, skip) && test(s)).length;
const activeFilterCount = () => state.boroughs.size + state.hoods.size + state.genres.size + state.vibes.size + (state.price !== 'any') + !!state.query;

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
const WHENS = [['tonight', 'Tonight'], ['tomorrow', 'Tomorrow'], ['weekend', 'This weekend'], ['week', 'Next 7 days'], ['twoweeks', 'Next 2 weeks']];

function renderDiscover() {
  view.innerHTML = `
    <h2>Where's the <em>music</em>?</h2>
    <div class="when">${WHENS.map(([k, l]) => `<button data-when="${k}" class="${state.when === k ? 'on' : ''}">${l}</button>`).join('')}</div>
    <div id="controls"></div>
    <div id="list"></div>`;
  renderControls();
  renderList();
}

function renderControls() {
  const hoods = [...new Set(VENUES.filter(v => state.boroughs.has(v.borough)).map(v => v.hood))].filter(h => !BOROUGHS.includes(h)).sort();
  const extra = +(state.price !== 'any');
  document.getElementById('controls').innerHTML = `
    ${chipRow('Borough', BOROUGHS, state.boroughs, 'borough', b => countFor('borough', s => s.venue.borough === b))}
    ${hoods.length ? chipRow('Neighborhood', hoods, state.hoods, 'hood', h => countFor('hood', s => s.venue.hood === h)) : ''}
    ${chipRow('Genre', GENRES, state.genres, 'genre', g => countFor('genre', s => s.genres.includes(g)))}
    ${chipRow('Vibe', VIBES, state.vibes, 'vibe', v => countFor('vibe', s => s.vibes.includes(v)))}
    <button class="filter-toggle" data-more>${state.moreFilters ? '− Fewer filters' : `+ Price${extra > 0 ? ` (${extra})` : ''}`}</button>
    ${state.moreFilters ? `
      <div class="filter-group"><div class="filter-label">Price</div><div class="chips">
        ${[['any', 'Any price'], ['u20', '$20 or less'], ['free', 'Free']].map(([k, l]) => `<button class="chip ${state.price === k ? 'on' : ''}" style="--c:${CHIP_COLORS.price}" data-price="${k}">${l}</button>`).join('')}
      </div></div>` : ''}
    <input class="search" id="search" type="search" placeholder="Search artist or venue" value="${state.query}">`;
}

function renderList() {
  const list = SHOWS.filter(s => matches(s));
  const el = document.getElementById('list');
  const head = `<div class="result-count"><span>${list.length} show${list.length === 1 ? '' : 's'}</span>${activeFilterCount() ? '<button data-clear>Clear filters</button>' : ''}</div>`;
  if (!list.length) {
    el.innerHTML = head + `<div class="empty"><b>Nothing matches</b>Try a wider timeframe or fewer filters.</div>`;
    return;
  }
  let html = head, lastDay = '';
  for (const s of list) {
    const k = midnight(s.start).getTime();
    if (k !== lastDay) { html += `<div class="day"><span class="day-name">${dayLabel(s.start)}</span><span class="day-date">${s.start.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</span></div>`; lastDay = k; }
    html += card(s);
  }
  el.innerHTML = html;
}

// ---------- Friends ----------
function renderFriends() {
  const { me } = Account;
  if (!me.profile) {
    view.innerHTML = `<h2>The <em>crew</em></h2>${accountPanel('See where your friends are going. Sign in to add them.')}`;
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
      <p>${pitch} No password — we'll email you a sign-in link.</p>
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

// ---------- My Shows ----------
function topOf(arr) {
  const c = {};
  arr.forEach(x => (c[x] = (c[x] || 0) + 1));
  return Object.entries(c).sort((a, b) => b[1] - a[1])[0]?.[0] || '—';
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
    </div>`).join('')}`;
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
    <p class="note">Shindig doesn't sell tickets — this opens the venue's own ticket page.</p>
  </div>`;
  sheet.classList.remove('hidden');
}
const closeSheet = () => sheet.classList.add('hidden');

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
  if (t.dataset.signout !== undefined) return Account.signOut();
  if (t.dataset.add) return Account.addFriend(t.dataset.add);
  if (t.dataset.unadd) return Account.removeFriend(t.dataset.unadd);
  if (t.dataset.open) return openSheet(t.dataset.open);
  if (t.dataset.when) { state.when = t.dataset.when; return renderDiscover(); }
  if (t.dataset.chip) {
    const set = { borough: state.boroughs, hood: state.hoods, genre: state.genres, vibe: state.vibes }[t.dataset.chip];
    toggle(set, t.dataset.val);
    if (t.dataset.chip === 'borough') {
      // drop neighborhoods that no longer belong to a selected borough
      for (const h of [...state.hoods]) if (!VENUES.some(v => v.hood === h && state.boroughs.has(v.borough))) state.hoods.delete(h);
    }
    renderControls(); return renderList();
  }
  if (t.dataset.price) { state.price = t.dataset.price; renderControls(); return renderList(); }
  if (t.dataset.more !== undefined) { state.moreFilters = !state.moreFilters; return renderControls(); }
  if (t.dataset.clear !== undefined) {
    state.boroughs.clear(); state.hoods.clear(); state.genres.clear(); state.vibes.clear(); state.price = 'any'; state.query = '';
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
  button.disabled = true;
  try {
    if (form.dataset.form === 'signin') {
      await Account.sendLink(f.get('email').trim());
      msg('signin-msg', 'Check your email for the sign-in link.');
    } else if (form.dataset.form === 'profile') {
      await Account.createProfile(f.get('username').trim().toLowerCase(), f.get('display').trim(), f.get('color'));
    } else if (form.dataset.form === 'find') {
      const name = f.get('username').trim();
      const person = await Account.findUser(name);
      if (!person) msg('find-result', `No one called @${name.replace(/^@/, '')} yet.`);
      else if (person.id === Account.me.profile.id) msg('find-result', 'That’s you!');
      else { await Account.addFriend(person.id); }
    }
  } catch (err) {
    msg({ signin: 'signin-msg', profile: 'profile-msg', find: 'find-result' }[form.dataset.form], err.message || 'Something went wrong.');
  } finally {
    button.disabled = false;
  }
});

document.addEventListener('input', e => {
  if (e.target.id === 'search') { state.query = e.target.value.trim(); renderList(); }
});
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeSheet(); });


if (UPDATED) {
  document.getElementById('updated').textContent =
    `Live · updated ${UPDATED.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`;
}
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
  const sheetId = !sheet.classList.contains('hidden') && sheet.querySelector('[data-id]')?.dataset.id;
  render();
  if (sheetId) openSheet(sheetId);
});

render();
Account.init();
