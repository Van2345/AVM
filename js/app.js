/* Assistance and Volunteer Management - ICCT Antipolo Campus
 * Frontend logic: navigation, theme, forms, fetch() calls to Django, map, modals. */
(function () {
'use strict';

const APP = window.APP || {};
// Campus coordinates - adjust these two numbers if the pin is not exactly on your campus.
const CAMPUS = [14.6255, 121.1222];
const STATUSES = ['PENDING', 'APPROVED', 'ASSIGNED', 'ONGOING', 'DONE', 'REJECTED', 'CANCELLED'];
const VSTATUSES = ['AVAILABLE', 'BUSY', 'UNAVAILABLE'];

/* ---------- helpers ---------- */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const cap = (s) => (s ? s.charAt(0) + s.slice(1).toLowerCase() : '');
const debounce = (fn, ms = 300) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };
let tileMaps = [];
const CONTACT_RE = /^[0-9+\-\s()]{7,20}$/;

function fmtDate(s) {
  if (!s) return '-';
  const d = new Date(String(s).replace(' ', 'T'));
  return isNaN(d) ? esc(s) : d.toLocaleString('en-PH', { dateStyle: 'medium', timeStyle: 'short' });
}
function toast(msg, type) {
  const box = $('#toasts');
  if (!box) return;
  const t = document.createElement('div');
  t.className = 'toast' + (type === 'err' ? ' err' : '');
  t.textContent = msg;
  box.appendChild(t);
  setTimeout(() => t.remove(), 4200);
}
async function api(url, opts = {}) {
  const method = opts.method || 'GET';
  const init = { method, credentials: 'same-origin', headers: { Accept: 'application/json' } };
  if (method !== 'GET') {
    init.headers['Content-Type'] = 'application/json';
    init.headers['X-CSRF-Token'] = APP.csrf;
    init.body = JSON.stringify(opts.body || {});
  }
  let res;
  try {
    res = await fetch(url, init);
  } catch {
    return { success: false, message: 'Could not connect to the server. Check your connection and try again.' };
  }
  if (res.status === 401 && APP.user) { location.reload(); }
  let data;
  try {
    data = await res.json();
  } catch {
    let message = 'The server returned an unexpected response. Please try again.';
    if (!res.ok) {
      if (res.status === 403) message = 'Your request was blocked. Refresh the page and try again.';
      else if (res.status === 404) message = 'This page could not be found. Refresh and try again.';
      else if (res.status === 429) message = 'Too many requests. Please wait a moment and try again.';
      else if (res.status >= 500) message = 'The server encountered a problem. Please try again.';
      else message = 'Your request could not be completed. Please check your information and try again.';
    }
    return { success: false, message };
  }
  if (!data || typeof data !== 'object' || Array.isArray(data)) {
    return { success: false, message: 'The server returned an unexpected response. Please try again.' };
  }
  if (!res.ok) {
    return { ...data, success: false, message: data.message || 'Your request could not be completed. Please try again.' };
  }
  return data;
}

/* ---------- dark / light mode ---------- */
function applyTheme(t) {
  document.documentElement.setAttribute('data-theme', t);
  try { localStorage.setItem('theme', t); } catch (e) { /* storage unavailable */ }
  $$('.switch').forEach((s) => s.setAttribute('aria-checked', String(t === 'dark')));
}
window.toggleTheme = function () {
  applyTheme(document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark');
  tileMaps.forEach(applyTiles);
};
applyTheme(document.documentElement.getAttribute('data-theme') || 'dark');
$$('.switch').forEach((s) => s.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); window.toggleTheme(); }
}));

/* ---------- show / hide password ---------- */
function addPwToggles(root) {
  $$('input[type=password]', root).forEach((inp) => {
    if (inp.parentElement.classList.contains('pw')) return;
    const wrap = document.createElement('div'); wrap.className = 'pw';
    inp.parentNode.insertBefore(wrap, inp); wrap.appendChild(inp);
    const b = document.createElement('button');
    b.type = 'button'; b.className = 'pw-btn'; b.textContent = 'Show'; b.setAttribute('aria-label', 'Show password');
    b.addEventListener('click', () => {
      const hidden = inp.type === 'password';
      inp.type = hidden ? 'text' : 'password';
      b.textContent = hidden ? 'Hide' : 'Show';
      b.setAttribute('aria-label', hidden ? 'Hide password' : 'Show password');
    });
    wrap.appendChild(b);
  });
}
addPwToggles(document);

/* ---------- map tiles (Esri basemaps: no API key needed; light / dark follow the theme) ---------- */
const ESRI = 'https://server.arcgisonline.com/ArcGIS/rest/services/';
const TILESETS = {
  light: [{ url: ESRI + 'World_Street_Map/MapServer/tile/{z}/{y}/{x}', native: 18 }],
  dark: [
    { url: ESRI + 'Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}', native: 16 },
    { url: ESRI + 'Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}', native: 16 },
  ],
};
const themeKey = () => (document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light');
function applyTiles(rec) {
  rec.layers.forEach((l) => rec.m.removeLayer(l));
  rec.layers = TILESETS[themeKey()].map((d) => L.tileLayer(d.url, {
    maxZoom: 19, maxNativeZoom: d.native, attribution: 'Tiles &copy; Esri &mdash; Esri, HERE, Garmin, OpenStreetMap contributors',
  }).addTo(rec.m));
}
function addTiles(m) {
  const rec = { m, layers: [] };
  tileMaps.push(rec);
  applyTiles(rec);
}

/* ---------- login / register screen ---------- */
if (!APP.user) {
  const setMsg = (text, good) => { const m = $('#authMsg'); m.textContent = text; m.className = 'auth-msg ' + (good ? 'ok' : 'err'); };
  const setTab = (name) => {
    $$('[data-auth-tab]').forEach((t) => t.classList.toggle('active', t.dataset.authTab === name));
    $('#loginForm').hidden = name !== 'login';
    $('#registerForm').hidden = name !== 'register';
    const m = $('#authMsg'); m.textContent = ''; m.className = 'auth-msg';
  };
  $$('[data-auth-tab]').forEach((t) => t.addEventListener('click', () => setTab(t.dataset.authTab)));

  $('#loginForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const username = $('#l_user').value.trim();
    const password = $('#l_pass').value;
    if (!username || !password) return setMsg('Please complete all required fields.', false);
    const btn = $('button[type=submit]', e.target); btn.disabled = true;
    const res = await api('/api/auth/login/', { method: 'POST', body: { username, password } });
    btn.disabled = false;
    if (res.success) { history.replaceState(null, '', location.pathname); location.reload(); }
    else setMsg(res.message || 'Invalid login credentials.', false);
  });

  $('#registerForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const body = {
      full_name: $('#r_name').value.trim(), username: $('#r_user').value.trim(), email: $('#r_email').value.trim(),
      password: $('#r_pass').value, confirm: $('#r_conf').value,
    };
    if (!body.full_name || !body.username || !body.password) return setMsg('Please complete all required fields.', false);
    if (!/^[A-Za-z0-9_.]{4,30}$/.test(body.username)) return setMsg('Username must be 4 to 30 characters (letters, numbers, dot or underscore).', false);
    if (body.password.length < 8) return setMsg('Password must be at least 8 characters.', false);
    if (body.password !== body.confirm) return setMsg('Passwords do not match.', false);
    const btn = $('button[type=submit]', e.target); btn.disabled = true;
    const res = await api('/api/auth/register/', { method: 'POST', body });
    btn.disabled = false;
    if (res.success) { e.target.reset(); setTab('login'); setMsg(res.message, true); }
    else setMsg(res.message || 'Unable to save data.', false);
  });
  return;
}

/* ---------- logged-in application ---------- */
const ROLE = APP.user.role;
const TITLES = { dash: APP.dashTitle, mapview: 'Live Map', request: 'Request Help', volunteer: 'Volunteers', manage: 'Manage' };
const reqCache = new Map();
const volCache = new Map();
let current = 'dash';

$('#todayLabel').textContent = new Date().toLocaleDateString('en-PH', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });

/* modal */
const modal = $('#modal');
function openModal(title, html, buttons) {
  $('#mTitle').textContent = title;
  $('#mBody').innerHTML = html;
  addPwToggles($('#mBody'));
  const foot = $('#mFoot'); foot.innerHTML = '';
  (buttons || [{ text: 'Close' }]).forEach((b) => {
    const el = document.createElement('button');
    el.type = 'button'; el.className = 'btn ' + (b.cls || 'btn-ghost'); el.textContent = b.text;
    el.addEventListener('click', () => (b.onClick ? b.onClick(el) : closeModal()));
    foot.appendChild(el);
  });
  modal.classList.add('open'); modal.setAttribute('aria-hidden', 'false');
  const f = $('#mBody input:not([type=radio]), #mBody select, #mBody textarea'); if (f) f.focus();
}
function closeModal() { modal.classList.remove('open'); modal.setAttribute('aria-hidden', 'true'); }
$('#mClose').addEventListener('click', closeModal);
modal.addEventListener('click', (e) => { if (e.target === modal) closeModal(); });
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeModal(); });
function confirmBox(message, okText) {
  return new Promise((resolve) => openModal('Please confirm', '<p>' + esc(message) + '</p>', [
    { text: 'Cancel', onClick: () => { closeModal(); resolve(false); } },
    { text: okText || 'Confirm', cls: 'btn-violet', onClick: () => { closeModal(); resolve(true); } },
  ]));
}

/* navigation */
const loaders = {
  dash: () => loadDashboard(),
  mapview: () => loadMap(),
  request: () => initPicker(),
  volunteer: () => loadVolunteers(),
  manage: () => loadManage(),
};
window.show = function (name) {
  if (!$('#p_' + name)) name = 'dash';
  current = name;
  $$('.page').forEach((p) => p.classList.toggle('active', p.id === 'p_' + name));
  $$('.menu button').forEach((b) => b.classList.toggle('active', b.id === 'm_' + name));
  $('#pageTitle').textContent = TITLES[name] || 'Dashboard';
  $('#sidebar').classList.remove('open');
  history.replaceState(null, '', '#' + name);
  window.scrollTo(0, 0);
  if (loaders[name]) loaders[name]();
};
const refresh = () => { if (loaders[current]) loaders[current](); };

$('#logoutBtn').addEventListener('click', async () => {
  await api('/api/auth/logout/', { method: 'POST', body: {} });
  history.replaceState(null, '', location.pathname);
  location.reload();
});

/* ---------- shared renderers ---------- */
const statusPill = (s) => '<span class="status s-' + esc(s.toLowerCase()) + '">' + esc(cap(s)) + '</span>';
const urgencyTag = (u) => '<span class="tag u-' + esc(u.toLowerCase()) + '">' + esc(u) + '</span>';

function actionsFor(r, full) {
  const s = r.status, out = [];
  const b = (act, text, cls) => '<button type="button" class="btn btn-sm ' + (cls || 'btn-ghost') + '" data-act="' + act + '" data-id="' + r.id + '">' + text + '</button>';
  out.push(b('view', 'View'));
  if (ROLE === 'ADMIN') {
    if (s === 'PENDING') out.push(b('approve', 'Approve', 'btn-violet'), b('reject', 'Reject'));
    if (s === 'APPROVED') out.push(b('assign', 'Assign', 'btn-violet'), b('reject', 'Reject'));
    if (s === 'ASSIGNED') out.push(b('start', 'Start'), b('complete', 'Complete', 'btn-violet'));
    if (s === 'ONGOING') out.push(b('complete', 'Complete', 'btn-violet'));
    if (['PENDING', 'APPROVED', 'ASSIGNED', 'ONGOING'].includes(s)) out.push(b('cancel', 'Cancel'));
    if (full) out.push(b('delete', 'Delete', 'btn-danger'));
  } else if (ROLE === 'VOLUNTEER') {
    if (s === 'ASSIGNED') out.push(b('start', 'Start assistance', 'btn-violet'));
    if (s === 'ONGOING') out.push(b('complete', 'Complete', 'btn-violet'));
  } else if (['PENDING', 'APPROVED'].includes(s)) {
    out.push(b('cancel', 'Cancel'));
  }
  return out.join('');
}
function requestRows(list, full) {
  if (!list.length) return '<tr class="empty"><td colspan="8">No requests found.</td></tr>';
  return list.map((r) => {
    reqCache.set(r.id, r);
    return '<tr>' +
      '<td data-label="Request ID"><b>' + esc(r.request_code) + '</b></td>' +
      '<td data-label="Requester">' + esc(r.requester_name) + '</td>' +
      '<td data-label="Type">' + esc(r.assistance_type) + '</td>' +
      '<td data-label="Location">' + esc(r.location) + '</td>' +
      '<td data-label="Urgency">' + urgencyTag(r.urgency) + '</td>' +
      '<td data-label="Status">' + statusPill(r.status) + '</td>' +
      '<td data-label="Volunteer">' + (r.volunteer_name ? esc(r.volunteer_name) : '<span class="muted">-</span>') + '</td>' +
      '<td data-label="Actions" class="acts">' + actionsFor(r, full) + '</td></tr>';
  }).join('');
}
function renderActivity(list) {
  const box = $('#actList');
  if (!list.length) { box.innerHTML = '<p class="muted small">No recent activity.</p>'; return; }
  box.innerHTML = list.map((a) => {
    const initial = esc((a.full_name || 'S').charAt(0).toUpperCase());
    return '<div class="list-item"><div class="avatar">' + initial + '</div><div><b>' + esc(a.details) + '</b><small>' +
      esc(a.full_name || 'System') + ' - ' + fmtDate(a.created_at) + '</small></div></div>';
  }).join('');
}
function renderChips(box, options, active, onChange) {
  box.innerHTML = options.map((o) => '<button type="button" class="chip' + (o === active ? ' active' : '') + '" data-v="' + o + '">' + (o === 'ALL' ? 'All' : cap(o)) + '</button>').join('');
  $$('.chip', box).forEach((c) => c.addEventListener('click', () => { onChange(c.dataset.v); renderChips(box, options, c.dataset.v, onChange); }));
}

/* ---------- request actions (event delegation) ---------- */
const CONFIRMS = {
  reject: 'Reject request {c}?',
  cancel: 'Cancel request {c}? Any assigned volunteer will be released.',
  complete: 'Mark request {c} as completed?',
  delete: 'Permanently delete request {c}? This cannot be undone.',
};
document.addEventListener('click', async (e) => {
  const btn = e.target.closest('[data-act]');
  if (!btn) return;
  const id = Number(btn.dataset.id), act = btn.dataset.act, r = reqCache.get(id);
  if (!r) return;
  if (act === 'view') return showRequest(r);
  if (act === 'assign') return openAssign(r);
  if (CONFIRMS[act] && !(await confirmBox(CONFIRMS[act].replace('{c}', r.request_code), cap(act)))) return;
  btn.disabled = true;
  const res = await api(act === 'delete' ? '/api/requests/delete/' : '/api/requests/update/', { method: 'POST', body: { id, action: act } });
  if (res.success) { toast(res.message); refresh(); } else { toast(res.message || 'Unable to save data.', 'err'); btn.disabled = false; }
});

function showRequest(r) {
  const row = (k, v) => '<dt>' + k + '</dt><dd>' + v + '</dd>';
  openModal(r.request_code, '<dl class="dl">' +
    row('Status', statusPill(r.status)) + row('Type', esc(r.assistance_type)) + row('Urgency', urgencyTag(r.urgency)) +
    row('Requester', esc(r.requester_name)) + row('Contact', esc(r.contact)) + row('Location', esc(r.location)) +
    row('Needed at', fmtDate(r.needed_at)) + row('Submitted', fmtDate(r.created_at)) +
    row('Volunteer', r.volunteer_name ? esc(r.volunteer_name) + ' (' + esc(r.volunteer_code) + ')' : '-') +
    row('Description', esc(r.description).replace(/\n/g, '<br>')) + '</dl>');
}
async function openAssign(r) {
  const res = await api('/api/volunteers/?status=AVAILABLE');
  if (!res.success) return toast(res.message, 'err');
  if (!res.volunteers.length) {
    return openModal('Assign volunteer', '<p class="muted">No volunteers are available right now. Set a volunteer to Available in the Volunteers page first.</p>');
  }
  const list = res.volunteers.map((v, i) =>
    '<label class="pick"><input type="radio" name="vol" value="' + v.id + '"' + (i === 0 ? ' checked' : '') + '><span><b>' + esc(v.full_name) +
    '</b> <small>' + esc(v.volunteer_code) + ' - ' + esc(v.skill) + '</small><br><small class="muted">' + esc(v.availability) + '</small></span></label>').join('');
  openModal('Assign volunteer', '<p class="muted small">' + esc(r.request_code) + ' - ' + esc(r.assistance_type) + ' - ' + esc(r.location) + '</p>' + list, [
    { text: 'Cancel' },
    { text: 'Assign volunteer', cls: 'btn-violet', onClick: async (el) => {
      const sel = $('input[name=vol]:checked', $('#mBody'));
      if (!sel) return toast('Please select a volunteer.', 'err');
      el.disabled = true;
      const out = await api('/api/requests/update/', { method: 'POST', body: { id: r.id, action: 'assign', volunteer_id: Number(sel.value) } });
      if (out.success) { closeModal(); toast(out.message); refresh(); } else { toast(out.message, 'err'); el.disabled = false; }
    } },
  ]);
}

/* ---------- dashboard ---------- */
async function loadDashboard() {
  const [s, r] = await Promise.all([api('/api/admin/dashboard/?action=stats'), api('/api/requests/?limit=8')]);
  if (s.success) {
    const v = s.volunteers, t = s.stats;
    const map = { k_total: t.total, k_pending: t.pending, k_approved: t.approved, k_assigned: t.assigned, k_ongoing: t.ongoing, k_done: t.done, k_vol: v.total, k_avail: v.available };
    Object.keys(map).forEach((id) => { $('#' + id).textContent = Number(map[id] || 0); });
    renderActivity(s.activities);
  } else toast(s.message || 'Unable to load data.', 'err');
  if (r.success) $('#dashReq').innerHTML = requestRows(r.requests, false);
}

/* ---------- live map ---------- */
let map, layerReq, layerVol;
const REQ_COLORS = { PENDING: '#eab308', APPROVED: '#3b82f6', ASSIGNED: '#06b6d4', ONGOING: '#7c3aed' };
const VOL_COLORS = { AVAILABLE: '#10b981', BUSY: '#f97316', UNAVAILABLE: '#94a3b8' };
function leafletReady(el) {
  if (typeof L !== 'undefined') return true;
  el.innerHTML = '<p class="muted" style="padding:20px">The map library could not be loaded. Check your internet connection.</p>';
  return false;
}
function fallbackPos(id) {
  const a = ((id * 137.5) % 360) * Math.PI / 180, d = 0.0006 + (id % 5) * 0.0002;
  return [CAMPUS[0] + Math.sin(a) * d, CAMPUS[1] + Math.cos(a) * d];
}
function initMap() {
  if (map) { map.invalidateSize(); return true; }
  if (!leafletReady($('#map'))) return false;
  map = L.map('map').setView(CAMPUS, 16);
  addTiles(map);
  L.circle(CAMPUS, { radius: 120, color: '#7c3aed', weight: 1, fillOpacity: 0.08 }).addTo(map);
  L.circleMarker(CAMPUS, { radius: 9, color: '#ffffff', weight: 2, fillColor: '#7c3aed', fillOpacity: 1 }).addTo(map).bindPopup('<b>ICCT Antipolo Campus</b>');
  layerReq = L.layerGroup().addTo(map);
  layerVol = L.layerGroup().addTo(map);
  const items = Object.keys(REQ_COLORS).map((k) => '<span><i style="background:' + REQ_COLORS[k] + '"></i>Request ' + cap(k) + '</span>');
  if (ROLE === 'ADMIN') items.push('<span><i style="background:' + VOL_COLORS.AVAILABLE + '"></i>Volunteer available</span><span><i style="background:' + VOL_COLORS.BUSY + '"></i>Volunteer busy</span>');
  items.unshift('<span><i style="background:#7c3aed"></i>Campus</span>');
  $('#legend').innerHTML = items.join('');
  return true;
}
async function loadMap() {
  if (!initMap()) return;
  setTimeout(() => map.invalidateSize(), 120);
  const jobs = [api('/api/requests/?map=1')];
  if (ROLE === 'ADMIN') jobs.push(api('/api/volunteers/?map=1'));
  const [rq, vl] = await Promise.all(jobs);
  layerReq.clearLayers(); layerVol.clearLayers();
  if (rq && rq.success) {
    rq.requests.forEach((r) => {
      const pos = r.latitude !== null && r.longitude !== null ? [r.latitude, r.longitude] : fallbackPos(r.id);
      L.circleMarker(pos, { radius: 8, color: '#ffffff', weight: 2, fillColor: REQ_COLORS[r.status] || '#64748b', fillOpacity: 0.95 })
        .bindPopup('<b>Request ID: ' + esc(r.request_code) + '</b><br>Type: ' + esc(r.assistance_type) + '<br>Status: ' + esc(r.status) + '<br>Urgency: ' + esc(r.urgency) + '<br>Location: ' + esc(r.location))
        .addTo(layerReq);
    });
  }
  if (vl && vl.success) {
    vl.volunteers.forEach((v) => {
      L.circleMarker([Number(v.latitude), Number(v.longitude)], { radius: 6, color: '#0f172a', weight: 2, fillColor: VOL_COLORS[v.status] || '#94a3b8', fillOpacity: 1 })
        .bindPopup('<b>Volunteer: ' + esc(v.volunteer_code) + '</b><br>' + esc(v.full_name) + '<br>Role: ' + esc(v.skill) + '<br>Status: ' + esc(v.status))
        .addTo(layerVol);
    });
  }
}

/* ---------- request form ---------- */
let pick, pinMarker;
function nowLocal() {
  const d = new Date(); d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
}
function setPin(lat, lng) {
  $('#rq_lat').value = Number(lat).toFixed(6);
  $('#rq_lng').value = Number(lng).toFixed(6);
  if (!pick) return;
  if (pinMarker) pinMarker.setLatLng([lat, lng]);
  else pinMarker = L.circleMarker([lat, lng], { radius: 9, color: '#ffffff', weight: 2, fillColor: '#ef4444', fillOpacity: 1 }).addTo(pick);
}
function clearPin() {
  $('#rq_lat').value = ''; $('#rq_lng').value = '';
  if (pinMarker && pick) { pick.removeLayer(pinMarker); pinMarker = null; }
}
function showRequestError(message) {
  const msg = $('#reqMsg');
  const field = [
    [/requester name/i, 'rq_name'],
    [/contact number/i, 'rq_contact'],
    [/assistance type/i, 'rq_type'],
    [/urgency/i, 'rq_urgency'],
    [/location/i, 'rq_location'],
    [/date and time/i, 'rq_time'],
    [/description/i, 'rq_desc'],
    [/map coordinates/i, 'rq_lat'],
  ].find(([pattern]) => pattern.test(message));
  msg.textContent = message;
  msg.className = 'auth-msg err';
  if (field) {
    const input = $('#' + field[1]);
    input.classList.add('invalid');
    input.setAttribute('aria-invalid', 'true');
    input.focus();
  }
}
function clearRequestError(event) {
  const input = event.target;
  if (!input.matches('input, select, textarea')) return;
  input.classList.remove('invalid');
  input.removeAttribute('aria-invalid');
  const msg = $('#reqMsg');
  if (msg.classList.contains('err')) {
    const remaining = $$('.invalid', $('#reqForm')).length;
    msg.textContent = remaining ? 'Please correct the highlighted fields.' : '';
    if (!remaining) msg.className = 'auth-msg';
  }
}
function initPicker() {
  if (!$('#rq_time').value) $('#rq_time').value = nowLocal();
  if (pick) { setTimeout(() => pick.invalidateSize(), 120); return; }
  if (!leafletReady($('#pickMap'))) return;
  pick = L.map('pickMap').setView(CAMPUS, 16);
  addTiles(pick);
  pick.on('click', (e) => setPin(e.latlng.lat, e.latlng.lng));
  setTimeout(() => pick.invalidateSize(), 120);
}
if ($('#reqForm')) {
  $('#reqForm').addEventListener('input', clearRequestError);
  $('#reqForm').addEventListener('change', clearRequestError);
  $('#clearPin').addEventListener('click', clearPin);
  $('#useGps').addEventListener('click', () => {
    if (!navigator.geolocation) return toast('Location is not supported on this device.', 'err');
    navigator.geolocation.getCurrentPosition((p) => { setPin(p.coords.latitude, p.coords.longitude); if (pick) pick.setView([p.coords.latitude, p.coords.longitude], 17); },
      () => toast('Unable to get your location. You can click the map instead.', 'err'), { enableHighAccuracy: true, timeout: 10000 });
  });
  $('#reqForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const msg = $('#reqMsg');
    const f = {
      requester_name: $('#rq_name').value.trim(), contact: $('#rq_contact').value.trim(), assistance_type: $('#rq_type').value,
      urgency: $('#rq_urgency').value, location: $('#rq_location').value.trim(), needed_at: $('#rq_time').value,
      description: $('#rq_desc').value.trim(), latitude: $('#rq_lat').value, longitude: $('#rq_lng').value,
    };
    $$('.invalid', e.target).forEach((x) => {
      x.classList.remove('invalid');
      x.removeAttribute('aria-invalid');
    });
    const checks = [
      ['rq_name', f.requester_name.length >= 2, 'requester name'],
      ['rq_contact', CONTACT_RE.test(f.contact), 'contact number'],
      ['rq_type', Boolean(f.assistance_type), 'assistance type'],
      ['rq_location', f.location.length >= 3, 'location'],
      ['rq_time', Boolean(f.needed_at), 'date and time'],
      ['rq_desc', f.description.length >= 5, 'description'],
    ];
    const bad = checks.filter(([, valid]) => !valid);
    if (bad.length) {
      bad.forEach(([id]) => {
        const input = $('#' + id);
        input.classList.add('invalid');
        input.setAttribute('aria-invalid', 'true');
      });
      showRequestError('Please check the highlighted fields: ' + bad.map(([, , label]) => label).join(', ') + '.');
      $('#' + bad[0][0]).focus();
      return;
    }
    msg.textContent = ''; msg.className = 'auth-msg';
    const btn = $('#reqSubmit'); btn.disabled = true;
    try {
      const res = await api('/api/requests/create/', { method: 'POST', body: f });
      if (res.success) {
        toast(res.message + ' Your Request ID is ' + res.request_code + '.');
        e.target.reset(); $('#rq_name').value = APP.user.name; clearPin(); $('#rq_time').value = nowLocal();
        show('dash');
      } else showRequestError(res.message || 'Unable to submit your request. Please try again.');
    } finally {
      btn.disabled = false;
    }
  });
}

/* ---------- volunteers (admin) ---------- */
let vFilter = 'ALL';
async function loadVolunteers() {
  if (!$('#vChips').children.length) renderChips($('#vChips'), ['ALL'].concat(VSTATUSES), vFilter, (v) => { vFilter = v; loadVolunteers(); });
  const q = $('#vSearch').value.trim();
  const res = await api('/api/volunteers/?q=' + encodeURIComponent(q) + (vFilter !== 'ALL' ? '&status=' + vFilter : ''));
  if (!res.success) return toast(res.message, 'err');
  volCache.clear();
  $('#volBody').innerHTML = res.volunteers.length ? res.volunteers.map((v) => {
    volCache.set(v.id, v);
    const opts = VSTATUSES.map((s) => '<option value="' + s + '"' + (s === v.status ? ' selected' : '') + '>' + cap(s) + '</option>').join('');
    return '<tr><td data-label="ID"><b>' + esc(v.volunteer_code) + '</b></td><td data-label="Name">' + esc(v.full_name) + '</td>' +
      '<td data-label="Contact">' + esc(v.contact) + '</td><td data-label="Skill / Role">' + esc(v.skill) + '</td>' +
      '<td data-label="Availability">' + esc(v.availability) + '</td>' +
      '<td data-label="Status"><select class="mini" data-vstatus="' + v.id + '">' + opts + '</select></td>' +
      '<td data-label="Actions" class="acts"><button type="button" class="btn btn-sm btn-ghost" data-vact="edit" data-id="' + v.id + '">Edit</button>' +
      '<button type="button" class="btn btn-sm btn-danger" data-vact="delete" data-id="' + v.id + '">Delete</button></td></tr>';
  }).join('') : '<tr class="empty"><td colspan="7">No volunteers found.</td></tr>';
}
function volunteerForm(v) {
  const isNew = !v.id;
  const stat = VSTATUSES.map((s) => '<option value="' + s + '"' + (s === (v.status || 'AVAILABLE') ? ' selected' : '') + '>' + cap(s) + '</option>').join('');
  return '<form id="vForm" novalidate>' +
    '<div class="row"><div class="field"><label for="vf_name">Full name *</label><input id="vf_name" maxlength="100" value="' + esc(v.full_name) + '"></div>' +
    '<div class="field"><label for="vf_contact">Contact number *</label><input id="vf_contact" maxlength="20" value="' + esc(v.contact) + '"></div></div>' +
    '<div class="row"><div class="field"><label for="vf_skill">Skill / Role *</label><input id="vf_skill" maxlength="80" value="' + esc(v.skill) + '"></div>' +
    '<div class="field"><label for="vf_avail">Availability *</label><input id="vf_avail" maxlength="100" placeholder="e.g. Mon-Fri 8:00 AM - 5:00 PM" value="' + esc(v.availability) + '"></div></div>' +
    '<div class="row three"><div class="field"><label for="vf_status">Status</label><select id="vf_status">' + stat + '</select></div>' +
    '<div class="field"><label for="vf_lat">Latitude</label><input id="vf_lat" value="' + esc(v.latitude) + '"></div>' +
    '<div class="field"><label for="vf_lng">Longitude</label><input id="vf_lng" value="' + esc(v.longitude) + '"></div></div>' +
    (isNew ? '<p class="muted small" style="margin-top:10px">Optional: create a login so this volunteer can see assigned requests.</p>' +
      '<div class="row"><div class="field"><label for="vf_user">Username</label><input id="vf_user" maxlength="30" autocomplete="off"></div>' +
      '<div class="field"><label for="vf_pass">Password (min. 8)</label><input id="vf_pass" type="password" autocomplete="new-password"></div></div>' : '') +
    '</form>';
}
function openVolunteerModal(v) {
  v = v || {};
  openModal(v.id ? 'Edit volunteer ' + v.volunteer_code : 'Add volunteer', volunteerForm(v), [
    { text: 'Cancel' },
    { text: 'Save', cls: 'btn-violet', onClick: async (el) => {
      const body = { full_name: $('#vf_name').value.trim(), contact: $('#vf_contact').value.trim(), skill: $('#vf_skill').value.trim(),
        availability: $('#vf_avail').value.trim(), status: $('#vf_status').value, latitude: $('#vf_lat').value.trim(), longitude: $('#vf_lng').value.trim() };
      if (!v.id) { body.username = $('#vf_user').value.trim(); body.password = $('#vf_pass').value; }
      if (!body.full_name || !body.contact || !body.skill || !body.availability) return toast('Please complete all required fields.', 'err');
      if (!CONTACT_RE.test(body.contact)) return toast('Please enter a valid contact number.', 'err');
      if (v.id) body.id = v.id;
      el.disabled = true;
      const res = await api(v.id ? '/api/volunteers/update/' : '/api/volunteers/create/', { method: 'POST', body });
      if (res.success) { closeModal(); toast(res.message); loadVolunteers(); } else { toast(res.message || 'Unable to save data.', 'err'); el.disabled = false; }
    } },
  ]);
}
if ($('#p_volunteer')) {
  $('#addVolunteer').addEventListener('click', () => openVolunteerModal());
  $('#vSearch').addEventListener('input', debounce(loadVolunteers));
  $('#volBody').addEventListener('change', async (e) => {
    const sel = e.target.closest('[data-vstatus]'); if (!sel) return;
    const res = await api('/api/volunteers/update/', { method: 'POST', body: { id: Number(sel.dataset.vstatus), action: 'status', status: sel.value } });
    toast(res.message || 'Unable to save data.', res.success ? undefined : 'err');
    if (!res.success) loadVolunteers();
  });
  $('#volBody').addEventListener('click', async (e) => {
    const b = e.target.closest('[data-vact]'); if (!b) return;
    const v = volCache.get(Number(b.dataset.id)); if (!v) return;
    if (b.dataset.vact === 'edit') return openVolunteerModal(v);
    if (!(await confirmBox('Delete volunteer ' + v.volunteer_code + ' (' + v.full_name + ')? Their login account will also be removed.', 'Delete'))) return;
    const res = await api('/api/volunteers/delete/', { method: 'POST', body: { id: v.id } });
    toast(res.message || 'Unable to save data.', res.success ? undefined : 'err');
    if (res.success) loadVolunteers();
  });
}

/* ---------- manage (admin) ---------- */
let mTab = 'req', mFilter = 'ALL';
async function loadManage() {
  if (!$('#mChips').children.length) renderChips($('#mChips'), ['ALL'].concat(STATUSES), mFilter, (v) => { mFilter = v; loadManage(); });
  ['req', 'users', 'logs'].forEach((t) => { $('#tab_' + t).hidden = t !== mTab; });
  $$('[data-tab]').forEach((b) => b.classList.toggle('active', b.dataset.tab === mTab));
  if (mTab === 'req') {
    const q = $('#mSearch').value.trim();
    const res = await api('/api/requests/?q=' + encodeURIComponent(q) + (mFilter !== 'ALL' ? '&status=' + mFilter : ''));
    if (res.success) $('#manageReq').innerHTML = requestRows(res.requests, true);
  } else if (mTab === 'users') {
    const res = await api('/api/admin/dashboard/?action=users');
    if (!res.success) return;
    $('#userBody').innerHTML = res.users.map((u) => {
      const self = u.id === APP.user.id, on = Number(u.is_active) === 1;
      return '<tr><td data-label="ID">' + u.id + '</td><td data-label="Name">' + esc(u.full_name) + '</td><td data-label="Username">' + esc(u.username) + '</td>' +
        '<td data-label="Email">' + esc(u.email || '-') + '</td><td data-label="Role">' + esc(cap(u.role)) + '</td>' +
        '<td data-label="Account"><span class="status ' + (on ? 's-available' : 's-cancelled') + '">' + (on ? 'Active' : 'Disabled') + '</span></td>' +
        '<td data-label="Actions" class="acts">' + (self ? '<span class="muted small">Current user</span>' :
          '<button type="button" class="btn btn-sm ' + (on ? 'btn-ghost' : 'btn-violet') + '" data-toggle-user="' + u.id + '">' + (on ? 'Disable' : 'Enable') + '</button>') + '</td></tr>';
    }).join('');
  } else {
    const res = await api('/api/admin/dashboard/?action=logs');
    if (!res.success) return;
    $('#logBody').innerHTML = res.logs.length ? res.logs.map((l) =>
      '<tr><td data-label="Time">' + fmtDate(l.created_at) + '</td><td data-label="User">' + esc(l.full_name || 'System') + '</td>' +
      '<td data-label="Action">' + esc(l.action) + '</td><td data-label="Details">' + esc(l.details) + '</td></tr>').join('')
      : '<tr class="empty"><td colspan="4">No activity yet.</td></tr>';
  }
}
if ($('#p_manage')) {
  $$('[data-tab]').forEach((b) => b.addEventListener('click', () => { mTab = b.dataset.tab; loadManage(); }));
  $('#mSearch').addEventListener('input', debounce(loadManage));
  $('#userBody').addEventListener('click', async (e) => {
    const b = e.target.closest('[data-toggle-user]'); if (!b) return;
    b.disabled = true;
    const res = await api('/api/admin/dashboard/', { method: 'POST', body: { action: 'toggle_user', id: Number(b.dataset.toggleUser) } });
    toast(res.message || 'Unable to save data.', res.success ? undefined : 'err');
    loadManage();
  });
}

/* ---------- start ---------- */
setInterval(() => { if (!document.hidden && !modal.classList.contains('open') && (current === 'dash' || current === 'mapview')) refresh(); }, 30000);
show((location.hash || '#dash').slice(1));
})();
