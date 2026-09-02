import './styles/continuity.css';

const SUPABASE_URL = 'https://ppbchnypnyscwkbmoiqv.supabase.co';
const PUBLISHABLE_KEY = 'sb_publishable_6xfEmDvcJvxO0fuNNA6E5g_fwCeDLe2';
const SESSION_KEY = 'falsetech-continuity-session';

const $ = (id) => document.getElementById(id);
const state = { session: null, overview: null };

function headers() {
  return {
    apikey: PUBLISHABLE_KEY,
    Authorization: `Bearer ${state.session?.access_token || ''}`,
    'Content-Type': 'application/json',
  };
}

function storeSession(session) {
  state.session = session;
  if (session) localStorage.setItem(SESSION_KEY, JSON.stringify(session));
  else localStorage.removeItem(SESSION_KEY);
}

async function authPassword(email, password) {
  const response = await fetch(`${SUPABASE_URL}/auth/v1/token?grant_type=password`, {
    method: 'POST',
    headers: { apikey: PUBLISHABLE_KEY, 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) throw new Error((await response.json()).error_description || 'Sign in failed.');
  const session = await response.json();
  storeSession(session);
  return session;
}

async function refreshSession() {
  if (!state.session?.refresh_token) throw new Error('No refresh token.');
  const response = await fetch(`${SUPABASE_URL}/auth/v1/token?grant_type=refresh_token`, {
    method: 'POST',
    headers: { apikey: PUBLISHABLE_KEY, 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: state.session.refresh_token }),
  });
  if (!response.ok) throw new Error('Session expired.');
  const session = await response.json();
  storeSession(session);
  return session;
}

async function rpc(name, body = {}, retry = true) {
  const response = await fetch(`${SUPABASE_URL}/rest/v1/rpc/${name}`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(body),
  });
  if (response.status === 401 && retry) {
    await refreshSession();
    return rpc(name, body, false);
  }
  if (!response.ok) throw new Error(await response.text());
  const text = await response.text();
  return text ? JSON.parse(text) : null;
}

function fmtTime(value) {
  if (!value) return 'Never';
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'short', timeStyle: 'short' }).format(new Date(value));
}

function escapeHtml(value = '') {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function renderOverview(data) {
  state.overview = data;
  $('summary-grid').innerHTML = `
    <article class="stat"><strong>${data.projects?.length || 0}</strong><span>Projects</span></article>
    <article class="stat"><strong>${data.artifact_count || 0}</strong><span>Files/artifacts</span></article>
    <article class="stat"><strong>${data.simlay_item_count || 0}</strong><span>SimLay items</span></article>
    <article class="stat"><strong>${data.open_conflicts || 0}</strong><span>Open conflicts</span></article>
  `;
  $('devices').innerHTML = (data.devices || []).map((device) => `
    <article class="row">
      <div><strong>${escapeHtml(device.display_name)}</strong><div class="muted">${escapeHtml(device.device_type)} · ${escapeHtml(device.hostname || 'No hostname')}</div></div>
      <div class="right"><span class="status ${device.status === 'active' ? 'ok' : ''}">${escapeHtml(device.status)}</span><small>${fmtTime(device.last_seen_at)}</small></div>
    </article>
  `).join('') || '<p class="muted">No devices registered yet.</p>';
  $('events').innerHTML = (data.recent_events || []).map((event) => `
    <article class="row">
      <div><strong>${escapeHtml(event.event_type)}</strong><div class="muted">${escapeHtml(event.project_name || 'FalseTech')} · ${escapeHtml(event.device_name || 'Unknown device')}</div></div>
      <small>${fmtTime(event.created_at)}</small>
    </article>
  `).join('') || '<p class="muted">No continuity events yet.</p>';
}

function renderSearch(data, query) {
  const projectRows = (data.projects || []).map((item) => `
    <article class="row"><div><span class="tag">PROJECT</span><strong>${escapeHtml(item.canonical_name)}</strong><div class="muted">${escapeHtml(item.canonical_repository || '')}</div></div></article>`);
  const artifactRows = (data.artifacts || []).map((item) => `
    <article class="row"><div><span class="tag">FILE</span><strong>${escapeHtml(item.canonical_name)}</strong><div class="muted">${escapeHtml(item.project_name || 'FalseTech')} · ${escapeHtml(item.source_device || 'Unknown device')}</div><small>${escapeHtml(item.original_path || '')}</small></div></article>`);
  const itemRows = (data.simlay_items || []).map((item) => `
    <article class="row"><div><span class="tag">SIMLAY</span><strong>${escapeHtml(item.final_name)}</strong><div class="muted">${escapeHtml(item.category || '')} · ${escapeHtml(item.status || '')}</div></div><div class="right">${item.asking_price != null ? `$${Number(item.asking_price).toFixed(2)}` : ''}</div></article>`);
  const rows = [...projectRows, ...artifactRows, ...itemRows];
  $('search-label').textContent = `${rows.length} result${rows.length === 1 ? '' : 's'} for “${query}”`;
  $('search-results').classList.remove('empty');
  $('search-results').innerHTML = rows.join('') || '<p class="muted">Nothing matched. Try another name, project, item, or old filename.</p>';
}

async function registerPhone() {
  await rpc('falsetech_device_upsert', {
    p_display_name: 'AJ-Phone',
    p_hostname: navigator.userAgent.includes('Android') ? 'Android Phone' : 'Phone',
    p_platform: navigator.userAgent,
    p_device_type: 'phone',
  });
}

async function loadApp() {
  await registerPhone();
  const overview = await rpc('falsetech_overview');
  renderOverview(overview);
  $('login-card').hidden = true;
  $('app-content').hidden = false;
  $('connection-pill').textContent = 'Connected';
  $('connection-pill').classList.add('connected');
}

async function attemptRestore() {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    if (!raw) return;
    state.session = JSON.parse(raw);
    await refreshSession();
    await loadApp();
  } catch {
    storeSession(null);
  }
}

$('sign-in').addEventListener('click', async () => {
  $('login-error').textContent = '';
  try {
    await authPassword($('email').value.trim(), $('password').value);
    $('password').value = '';
    await loadApp();
  } catch (error) {
    $('login-error').textContent = error.message || String(error);
  }
});

$('refresh-button').addEventListener('click', async () => {
  renderOverview(await rpc('falsetech_overview'));
});

async function runSearch() {
  const query = $('search-input').value.trim();
  if (!query) return;
  renderSearch(await rpc('falsetech_search', { p_query: query, p_limit: 50 }), query);
}

$('search-button').addEventListener('click', runSearch);
$('search-input').addEventListener('keydown', (event) => { if (event.key === 'Enter') runSearch(); });
$('sign-out').addEventListener('click', () => {
  storeSession(null);
  $('app-content').hidden = true;
  $('login-card').hidden = false;
  $('connection-pill').textContent = 'Signed out';
  $('connection-pill').classList.remove('connected');
});

attemptRestore();
