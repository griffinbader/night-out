// Accounts: sign-in (email link), profiles, friends and syncing plans — backed by Supabase.
// Privacy rules live in the database (supabase/schema.sql): you only ever receive
// your own plans and those of mutual friends.

const Account = (() => {
  const PROFILE_COLS = 'id, username, display_name, color';
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
      const { data: profile } = await db.from('profiles').select(PROFILE_COLS).eq('id', me.user.id).maybeSingle();
      me.profile = profile;
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

    async signOut() { await db.auth.signOut(); },

    // Permanently removes the account: sign-in record, profile, plans and friend connections.
    async deleteAccount() {
      const { error } = await db.rpc('delete_my_account');
      if (error) throw new Error('Couldn’t delete your account. Try again, or email griffin@ctownsounds.com.');
      await db.auth.signOut();
    },

    async createProfile(username, displayName, color) {
      const { error } = await db.from('profiles').insert({ id: me.user.id, username, display_name: displayName, color });
      if (error) throw new Error(error.code === '23505' ? 'That username is taken.' : error.message);
      await refresh();
    },

    // status: 'going' | 'interested' | null (remove)
    async setPlan(show, status) {
      if (!me.profile) return;
      const uid = me.user.id;
      me.myPlans = me.myPlans.filter(p => p.show_id !== show.id);
      if (status) {
        const row = { user_id: uid, show_id: show.id, status, show: snapshot(show), show_start: show.start.toISOString(), updated_at: new Date().toISOString() };
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
      }));
      const { error } = await db.from('plans').upsert(rows, { ignoreDuplicates: true });
      if (error) console.error(error);
      await loadSocial(); changed();
    },

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
    async logVisit(ref) {
      if (!db) return;
      const last = +(localGet('no.lastVisit') || 0);
      if (Date.now() - last < 30 * 60e3) return;
      localSet('no.lastVisit', String(Date.now()));
      const { error } = await db.from('visits').insert({ device_id: deviceId(), user_id: me.user?.id || null, ref: ref || null });
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
