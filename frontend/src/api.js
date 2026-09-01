const API_BASE = (window.SIMLAY_API_BASE || import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000').replace(/\/$/, '');

export function downloadUrl(exportId) {
  return `${API_BASE}/api/exports/download/${exportId}`;
}

export async function api(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, options);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  const contentType = res.headers.get('content-type') || '';
  if (!contentType.includes('application/json')) return res.text();
  return res.json();
}

function itemListPath(runId, options = {}) {
  const params = new URLSearchParams();
  if (options.owner && options.owner !== 'All') params.set('owner', options.owner);
  if (options.includeDeleted) params.set('include_deleted', 'true');
  const query = params.toString();
  return `/api/items/${runId}${query ? `?${query}` : ''}`;
}

export const SimLayApi = {
  health: () => api('/'),
  createRun: (payload) => api('/api/runs', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload) }),
  listRuns: () => api('/api/runs'),
  getRun: (runId) => api(`/api/runs/${runId}`),
  listProfiles: () => api('/api/profiles'),
  getProfile: (name) => api(`/api/profiles/${name}`),
  uploadMedia: async (runId, files) => {
    const form = new FormData();
    [...files].forEach((file) => form.append('files', file));
    return api(`/api/media/upload/${runId}`, { method: 'POST', body: form });
  },
  listMedia: (runId) => api(`/api/media/${runId}`),
  processRun: (runId, provider = 'mock') => api(`/api/process/${runId}?provider=${encodeURIComponent(provider)}`, { method: 'POST' }),
  analyzeOcrUpload: async (files, provider = 'mock', options = {}) => {
    const form = new FormData();
    [...files].forEach(f => form.append('files', f));
    if (options.mergeLevel) form.append('merge_level', options.mergeLevel);
    if (options.returnRawOcr !== undefined) form.append('return_raw_ocr', String(options.returnRawOcr));
    return api(`/api/ocr/analyze-upload?provider=${encodeURIComponent(provider)}`, { method: 'POST', body: form });
  },
  analyzeRunOcr: (runId, provider = 'mock', options = {}) => {
    const params = new URLSearchParams({ provider });
    if (options.mergeLevel) params.set('merge_level', options.mergeLevel);
    if (options.saveItems !== undefined) params.set('save_items', String(options.saveItems));
    if (options.returnRawOcr !== undefined) params.set('return_raw_ocr', String(options.returnRawOcr));
    return api(`/api/ocr/run/${runId}?${params.toString()}`, { method: 'POST' });
  },
  ocrHealth: (provider = 'mock') => api(`/api/ocr/health?provider=${encodeURIComponent(provider)}`),
  listItems: (runId, options = {}) => api(itemListPath(runId, options)),
  getItem: (itemId) => api(`/api/items/detail/${itemId}`),
  inventorySummary: (runId) => api(`/api/items/run/${runId}/summary`),
  createItem: (payload) => api('/api/items', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload) }),
  updateItem: (itemId, payload) => api(`/api/items/${itemId}`, { method: 'PATCH', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload) }),
  deleteItem: (itemId, reason = '') => {
    const params = new URLSearchParams({ confirm: 'true' });
    if (reason) params.set('reason', reason);
    return api(`/api/items/${itemId}?${params.toString()}`, { method: 'DELETE' });
  },
  restoreItem: (itemId) => api(`/api/items/${itemId}/restore`, { method: 'POST' }),
  duplicateItem: (itemId, payload = {}) => api(`/api/items/${itemId}/duplicate`, {
    method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload),
  }),
  valueItem: (itemId) => api(`/api/items/${itemId}/value`, { method: 'POST' }),
  addEvidence: (payload) => api('/api/evidence', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload) }),
  listEvidence: (itemId) => api(`/api/evidence/item/${itemId}`),
  addScreenshotEvidence: async ({ item_id, file, listing_type, platform, notes, ocr_text }) => {
    const form = new FormData();
    form.append('item_id', item_id);
    form.append('file', file);
    form.append('listing_type', listing_type || 'sold');
    if (platform) form.append('platform', platform);
    if (notes) form.append('notes', notes);
    if (ocr_text) form.append('ocr_text', ocr_text);
    return api('/api/evidence/screenshot', { method: 'POST', body: form });
  },
  refreshEvidence: (evidenceId) => api(`/api/evidence/${evidenceId}/refresh`, { method: 'POST' }),
  refreshRunEvidence: (runId) => api(`/api/evidence/run/${runId}/refresh`, { method: 'POST' }),
  ebayStatus: () => api('/api/connectors/ebay/status'),
  exportCsv: (runId) => api(`/api/exports/csv/${runId}`, { method: 'POST' }),
  exportAudit: (runId) => api(`/api/exports/audit/${runId}`, { method: 'POST' }),
};

export async function listItems(runId, options = {}) {
  return api(itemListPath(runId, options));
}

export async function listMedia(runId) {
  const res = await fetch(`${API_BASE}/api/media/${runId}`);
  if (!res.ok) throw new Error(`Failed to load media: ${res.status}`);
  return res.json();
}

export async function uploadOneMedia(runId, file) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/api/media/upload-one/${runId}`, { method: "POST", body: form });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Upload failed: ${res.status} ${text}`);
  }
  return res.json();
}

export function mediaUrl(filePath) {
  if (!filePath) return "";
  const cleaned = filePath
    .replaceAll("\\", "/")
    .replace(/^data\/uploads\//, "uploads/")
    .replace(/^backend\/data\/uploads\//, "uploads/");
  return `${API_BASE}/${cleaned}`;
}
