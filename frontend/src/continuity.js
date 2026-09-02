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

async function parseAuthError(response, fallback) {
  try {
    const data = await response.json();
    return data.error_description || data.msg || data.message || fallback;
  } catch {
    return fallback;
  }
}

async function authPassword(email, password) {
  const response = await fetch(`${SUPABASE_URL}/auth/v1/token?grant_type=password`, {
    method: 'POST',
    headers: { apikey: PUBLISHABLE_KEY, 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) throw new Error(await parseAuthError(response, 'Sign in failed.'));
  const session = await response.json();
  storeSession(session);
  return session;
}

async function createAccount(email, password) {
  if (password.length < 8) throw new Error('Use a password of at least 8 characters.');
  const response = await fetch(`${SUPABASE_URL}/auth/v1/signup`, {
    method: 'POST',
    headers: { apikey: PUBLISHABLE_KEY, 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, data: { product: 'FalseTech Continuity' } }),
  });
  if (!response.ok) throw new Error(await parseAuthError(response, 'Account creation failed.'));
  const session = await response.json();
  if (session.access_token && session.refresh_token) {
    storeSession(session);
    return { signedIn: true, message: 'FalseTech account created. This phone is connected.' };
  }
  return { signedIn: false, message: 'Account created. Confirm the verification email once, then tap Sign in.' };
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
    <article class="row">
      <div><span class="tag">FILE</span><strong>${escapeHtml(item.canonical_name)}</strong><div class="muted">${escapeHtml(item.project_name || 'FalseTech')} · ${escapeHtml(item.source_device || 'Unknown device')}</div><small>${escapeHtml(item.original_path || '')}</small></div>
      ${item.canonical_uri ? `<button class="download-file secondary" data-uri="${escapeHtml(encodeURIComponent(item.canonical_uri))}" data-name="${escapeHtml(encodeURIComponent(item.canonical_name))}">Open</button>` : '<span class="muted">Metadata only</span>'}
    </article>`);
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
  renderOverview(await rpc('falsetech_overview'));
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

async function downloadArtifact(uri, name) {
  const prefix = 'storage://falsetech-files/';
  if (!uri.startsWith(prefix)) throw new Error('This file is metadata-only and has no private storage copy.');
  const key = uri.slice(prefix.length).split('/').map(encodeURIComponent).join('/');
  let response = await fetch(`${SUPABASE_URL}/storage/v1/object/authenticated/falsetech-files/${key}`, {
    headers: { apikey: PUBLISHABLE_KEY, Authorization: `Bearer ${state.session.access_token}` },
  });
  if (response.status === 401) {
    await refreshSession();
    response = await fetch(`${SUPABASE_URL}/storage/v1/object/authenticated/falsetech-files/${key}`, {
      headers: { apikey: PUBLISHABLE_KEY, Authorization: `Bearer ${state.session.access_token}` },
    });
  }
  if (!response.ok) throw new Error('Could not open the private FalseTech file.');
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = name;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 30000);
}

$('sign-in').addEventListener('click', async () => {
  $('login-error').textContent = '';
  $('login-message').textContent = '';
  try {
    await authPassword($('email').value.trim(), $('password').value);
    $('password').value = '';
    await loadApp();
  } catch (error) {
    $('login-error').textContent = error.message || String(error);
  }
});

$('create-account').addEventListener('click', async () => {
  $('login-error').textContent = '';
  $('login-message').textContent = '';
  try {
    const result = await createAccount($('email').value.trim(), $('password').value);
    $('login-message').textContent = result.message;
    if (result.signedIn) {
      $('password').value = '';
      await loadApp();
    }
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
$('search-results').addEventListener('click', async (event) => {
  const button = event.target.closest('.download-file');
  if (!button) return;
  button.disabled = true;
  try {
    await downloadArtifact(decodeURIComponent(button.dataset.uri), decodeURIComponent(button.dataset.name));
  } catch (error) {
    $('search-label').textContent = error.message || String(error);
  } finally {
    button.disabled = false;
  }
});
$('sign-out').addEventListener('click', () => {
  storeSession(null);
  $('app-content').hidden = true;
  $('login-card').hidden = false;
  $('connection-pill').textContent = 'Signed out';
  $('connection-pill').classList.remove('connected');
});

attemptRestore();
