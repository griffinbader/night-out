// Accounts: sign-in (email link), profiles, friends and syncing plans — backed by Supabase.
// Privacy rules live in the database (supabase/schema.sql): you only ever receive
// your own plans and those of mutual friends.

const Account = (() => {
  const PROFILE_COLS = 'id, username, display_name, color, avatar';
  const cfg = window.NIGHT_OUT_CONFIG || {};
  const db = window.supabase && cfg.supabaseUrl ? window.supabase.createClient(cfg.supabaseUrl, cfg.supabaseKey) : null;

  const me = {
    ready: false,
    user: null,       // Supabase auth user
    profile: null,    // { id, username, display_name, color }
    friends: [],      // mutual adds, as profiles
    incoming: [],     // added me, I haven't added back
    outgoing: [],     // I added them, waiting on them
    friendPlans: [],  // [{ user_id, show_id, status, show, show_start }]
    myPlans: [],      // same shape, mine
  };
  const localGet = k => { try { return localStorage.getItem(k); } catch { return null; } };
  const localSet = (k, v) => { try { localStorage.setItem(k, v); } catch { /* storage unavailable — fine */ } };
  // A random code for this browser, so return visits can be counted before someone signs in.
  const deviceId = () => {
    let id = localGet('no.device');
    if (!id) { id = (crypto.randomUUID?.() || Math.random().toString(36).slice(2) + Date.now().toString(36)); localSet('no.device', id); }
    return id;
  };

  const privacy = new Map(); // show id -> private, remembered while switching between going and interested

  const listeners = [];
  const changed = () => listeners.forEach(fn => fn());

  const profileById = id => me.friends.find(p => p.id === id) || me.incoming.find(p => p.id === id) || (me.profile?.id === id ? me.profile : null);

  // A copy of the listing saved with each plan, so history survives after a show leaves the listings.
  const snapshot = s => ({
    artist: s.artist, support: s.support, venue: s.venue.id, start: s.start.toISOString(),
    image: s.image || null, genres: s.genres, price: s.price ?? null, url: s.url || null,
  });

  async function refresh() {
    if (!db) return;
    const { data: { session } } = await db.auth.getSession();
    me.user = session?.user || null;
    me.profile = null; me.friends = []; me.incoming = []; me.outgoing = []; me.friendPlans = []; me.myPlans = [];
    if (me.user) {
      const { data: profile, error } = await db.from('profiles').select(PROFILE_COLS).eq('id', me.user.id).maybeSingle();
      if (error) { console.error(error); me.ready = true; return changed(); } // never mistake a failed read for "no profile yet"
      me.profile = profile;
      if (profile) { // optional setting: a missing permission must not break sign-in
        const { data: extra } = await db.from('profiles').select('plans_private').eq('id', me.user.id).maybeSingle();
        profile.plans_private = !!extra?.plans_private;
      }
      if (profile) await loadSocial();
    }
    me.ready = true;
    changed();
  }

  async function loadSocial() {
    const uid = me.user.id;
    const [{ data: follows }, { data: mine }] = await Promise.all([
      db.from('follows').select('follower_id, followee_id'),
      db.from('plans').select('*').eq('user_id', uid),
    ]);
    me.myPlans = mine || [];
    const iAdded = new Set((follows || []).filter(f => f.follower_id === uid).map(f => f.followee_id));
    const addedMe = new Set((follows || []).filter(f => f.followee_id === uid).map(f => f.follower_id));
    const ids = [...new Set([...iAdded, ...addedMe])];
    const { data: people } = ids.length ? await db.from('profiles').select(PROFILE_COLS).in('id', ids) : { data: [] };
    const byId = Object.fromEntries((people || []).map(p => [p.id, p]));
    me.friends = ids.filter(id => iAdded.has(id) && addedMe.has(id)).map(id => byId[id]).filter(Boolean);
    me.incoming = [...addedMe].filter(id => !iAdded.has(id)).map(id => byId[id]).filter(Boolean);
    me.outgoing = [...iAdded].filter(id => !addedMe.has(id)).map(id => byId[id]).filter(Boolean);
    if (me.friends.length) {
      const { data: plans } = await db.from('plans').select('*').in('user_id', me.friends.map(f => f.id));
      me.friendPlans = plans || [];
    }
  }

  return {
    me,
    enabled: !!db,
    onChange: fn => listeners.push(fn),
    profileById,

    async init() {
      if (!db) { me.ready = true; return changed(); }
      db.auth.onAuthStateChange(event => {
        if (event === 'SIGNED_IN' || event === 'SIGNED_OUT') setTimeout(refresh, 0);
      });
      await refresh();
    },

    async sendLink(email) {
      const { error } = await db.auth.signInWithOtp({
        email, options: { emailRedirectTo: location.origin + location.pathname },
      });
      if (error) throw error;
    },

    // The code in the sign-in email. Needed on iPhone home-screen apps, where the email link opens Safari instead.
    async verifyCode(email, token) {
      const { error } = await db.auth.verifyOtp({ email, token, type: 'email' });
      if (error) throw new Error(/expired|invalid/i.test(error.message) ? 'That code didn’t work. Check it, or send a new one.' : error.message);
    },

    async signOut() { await db.auth.signOut(); },

    // Permanently removes the account: sign-in record, profile, plans and friend connections.
    async deleteAccount() {
      const { error } = await db.rpc('delete_my_account');
      if (error) throw new Error('Couldn’t delete your account. Try again, or email griffin@ctownsounds.com.');
      await db.auth.signOut();
    },

    // Join with just a name and a character: a guest account on this phone, no email (Supabase anonymous sign-in).
    // Email can be added later from Profile to keep the account on other devices.
    // Returns 'existing' when the email already has an account (we've emailed them a sign-in code instead).
    async join(displayName, avatarEmoji, email) {
      if (!me.user) {
        const { error } = await db.auth.signInAnonymously();
        if (error) throw new Error('Couldn’t start your account. Try again in a moment.');
        const { data: { session } } = await db.auth.getSession();
        me.user = session?.user || null;
      }
      if (email && me.user?.is_anonymous) {
        // Attach the email right away. They're in now; the confirmation email can be tapped whenever.
        const { error } = await db.auth.updateUser({ email }, { emailRedirectTo: location.origin + location.pathname });
        if (error && /already|registered|exists/i.test(error.message)) {
          await db.auth.signOut();
          await this.sendLink(email);
          return 'existing';
        }
        if (error) console.warn('email not attached yet', error.message); // don't block joining over it
      }
      const base = displayName.toLowerCase().normalize('NFD').replace(/[^a-z0-9]/g, '').slice(0, 14) || 'friend';
      const palette = ['#ffd23f', '#ff9ccf', '#22c07a', '#b8a2ff', '#6f86ff', '#ff9f1c', '#ff4d2e'];
      const color = palette[Math.floor(Math.random() * palette.length)];
      for (let tries = 0; tries < 6; tries++) { // usernames are made for people; retry on the rare clash
        const username = (base.length >= 3 ? base : base + 'fan') + '_' + Math.floor(100 + Math.random() * 900);
        const { error } = await db.from('profiles').insert({ id: me.user.id, username, display_name: displayName, color, avatar: avatarEmoji });
        if (!error) { await refresh(); return 'joined'; }
        if (error.code === '23505' && /pkey/.test(error.message)) { await refresh(); return 'joined'; } // already has a profile
        if (error.code !== '23505') throw new Error(error.message);
      }
      throw new Error('Couldn’t save that. Try again.');
    },

    isGuest: () => !!me.user?.is_anonymous,
    pendingEmail: () => me.user?.new_email || null, // attached but not confirmed yet

    // Guests: attach an email so the account works on other phones. Supabase emails a confirmation link.
    async addEmail(email) {
      const { error } = await db.auth.updateUser({ email }, { emailRedirectTo: location.origin + location.pathname });
      if (error) throw new Error(/already/i.test(error.message) ? 'That email already has a shindig account. Sign out and sign in with it instead.' : error.message);
    },

    async createProfile(username, displayName, color) {
      const { error } = await db.from('profiles').insert({ id: me.user.id, username, display_name: displayName, color });
      if (error?.code === '23505' && /pkey/.test(error.message)) { await refresh(); return; } // you already have a profile
      if (error) throw new Error(error.code === '23505' ? 'That username is taken.' : error.message);
      await refresh();
    },

    // status: 'going' | 'interested' | null (remove)
    async setPlan(show, status) {
      if (!me.profile) return;
      const uid = me.user.id;
      const existing = me.myPlans.find(p => p.show_id === show.id);
      if (existing) privacy.set(show.id, !!existing.private); // switching going <-> interested keeps its privacy
      me.myPlans = me.myPlans.filter(p => p.show_id !== show.id);
      if (status) {
        const row = { user_id: uid, show_id: show.id, status, show: snapshot(show), show_start: show.start.toISOString(),
          updated_at: new Date().toISOString(), private: privacy.get(show.id) ?? !!me.profile.plans_private };
        me.myPlans.push(row);
        const { error } = await db.from('plans').upsert(row);
        if (error) console.error(error);
      } else {
        const { error } = await db.from('plans').delete().eq('user_id', uid).eq('show_id', show.id);
        if (error) console.error(error);
      }
    },

    // Upload picks made before signing in (show objects + status).
    async importPlans(items) {
      if (!me.profile || !items.length) return;
      const uid = me.user.id;
      const rows = items.map(({ show, status }) => ({
        user_id: uid, show_id: show.id, status, show: snapshot(show), show_start: show.start.toISOString(),
        private: !!me.profile.plans_private,
      }));
      const { error } = await db.from('plans').upsert(rows, { ignoreDuplicates: true });
      if (error) console.error(error);
      await loadSocial(); changed();
    },

    // One plan: visible to friends, or only to you.
    async setPlanPrivate(showId, isPrivate) {
      const plan = me.myPlans.find(p => p.show_id === showId);
      if (!plan) return;
      plan.private = isPrivate;
      privacy.set(showId, isPrivate);
      const { error } = await db.from('plans').update({ private: isPrivate }).eq('user_id', me.user.id).eq('show_id', showId);
      if (error) throw new Error('Couldn’t change that. Try again.');
      changed();
    },

    // Account setting: whether new plans start private.
    async setPlansPrivateDefault(isPrivate) {
      const { error } = await db.from('profiles').update({ plans_private: isPrivate }).eq('id', me.user.id);
      if (error) throw new Error('Couldn’t save that setting. Try again.');
      me.profile.plans_private = isPrivate;
      changed();
    },

    isPrivate: showId => !!me.myPlans.find(p => p.show_id === showId)?.private,

    async inviteLink() {
      const { data, error } = await db.rpc('my_invite_code');
      if (error || !data) throw new Error('Couldn’t make your invite link. Try again in a moment.');
      return `${location.origin}${location.pathname}#invite=${data}`;
    },

    // Opening someone's invite link: become friends both ways. Returns the inviter's profile bits.
    async acceptInvite(code) {
      const { data, error } = await db.rpc('accept_invite', { code });
      if (error) throw new Error(error.message);
      await loadSocial(); changed();
      return data;
    },

    async findUser(username) {
      const { data } = await db.from('profiles').select(PROFILE_COLS).eq('username', username.toLowerCase().replace(/^@/, '')).maybeSingle();
      return data;
    },

    async addFriend(id) {
      const { error } = await db.from('follows').insert({ follower_id: me.user.id, followee_id: id });
      if (error && error.code !== '23505') throw error;
      await loadSocial(); changed();
    },

    async removeFriend(id) {
      await db.from('follows').delete().eq('follower_id', me.user.id).eq('followee_id', id);
      await loadSocial(); changed();
    },

    // Visit log for the test group: one row per device every 30 minutes at most (supabase/testing.sql).
    async logVisit(ref, installed = false) {
      if (!db) return;
      const last = +(localGet('no.lastVisit') || 0);
      if (Date.now() - last < 30 * 60e3) return;
      localSet('no.lastVisit', String(Date.now()));
      const row = { device_id: deviceId(), user_id: me.user?.id || null, ref: ref || null, installed };
      let { error } = await db.from('visits').insert(row);
      if (error && /installed/.test(error.message)) { // database not updated for the installed column yet
        delete row.installed;
        ({ error } = await db.from('visits').insert(row));
      }
      if (error) console.warn('visit not logged', error.message);
    },

    // kind: 'wrong_info' | 'not_artist' | 'cancelled' | 'other' | 'missing'
    async report({ kind, showId = null, showLabel = null, details = null }) {
      if (!db) throw new Error('Couldn’t send that. Email griffin@ctownsounds.com instead.');
      const { error } = await db.from('reports').insert({
        kind, show_id: showId, show_label: showLabel, details: details || null, device_id: deviceId(), user_id: me.user?.id || null,
      });
      if (error) throw new Error('Couldn’t send that. Try again, or email griffin@ctownsounds.com.');
    },
  };
})();
