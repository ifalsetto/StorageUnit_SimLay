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

export const SimLayApi = {
  health: () => api('/'),
  createRun: (payload) => api('/api/runs', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload) }),
  listRuns: () => api('/api/runs'),
  getRun: (runId) => api(`/api/runs/${runId}`),
  listProfiles: () => api('/api/profiles'),
  getProfile: (name) => api(`/api/profiles/${name}`),
  uploadMedia: async (runId, files) => {
    const form = new FormData();
    [...files].forEach(f => form.append('files', f));
    return api(`/api/media/upload/${runId}`, { method: 'POST', body: form });
  },
  listMedia: (runId) => api(`/api/media/${runId}`),
  processRun: (runId, provider = 'mock') => api(`/api/process/${runId}?provider=${encodeURIComponent(provider)}`, { method: 'POST' }),
  listItems: (runId) => api(`/api/items/${runId}`),
  getItem: (itemId) => api(`/api/items/detail/${itemId}`),
  createItem: (payload) => api('/api/items', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload) }),
  updateItem: (itemId, payload) => api(`/api/items/${itemId}`, { method: 'PATCH', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload) }),
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
