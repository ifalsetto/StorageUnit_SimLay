import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { SimLayApi, downloadUrl } from './api';
import InventoryPanel from "./InventoryPanel";
import './styles/main.css';

const DEFAULT_ITEM = {
  final_name: '',
  raw_name: '',
  brand: '',
  category: '',
  quantity: 1,
  visible_condition: 'Unknown',
  confidence: 'Inferred',
  confidence_reason: '',
  source: 'User Visual',
  notes: '',
};

const DEFAULT_EVIDENCE = {
  item_id: '',
  source_type: 'url',
  source_name: 'user_url',
  url: '',
  url_title: '',
  url_platform: '',
  price: '',
  condition: '',
  sale_date: '',
  listing_type: 'sold',
  is_bundle: false,
  notes: '',
};

const tabs = [
  { id: 'dashboard', label: 'Command', icon: '⌁' },
  { id: 'intake', label: 'Intake', icon: '▣' },
  { id: 'review', label: 'Review', icon: '◇' },
  { id: 'evidence', label: 'Evidence', icon: '◌' },
  { id: 'export', label: 'Export', icon: '⇩' },
  { id: 'settings', label: 'Deploy', icon: '⚙' },
];

function money(value) {
  if (value === null || value === undefined || value === '') return '—';
  const n = Number(value);
  if (Number.isNaN(n)) return '—';
  return `$${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function classForConfidence(value) {
  if (value === 'Verified') return 'good';
  if (value === 'Unknown') return 'danger';
  return 'warn';
}

function classForStatus(status) {
  if (status === 'completed') return 'good';
  if (status === 'failed') return 'danger';
  if (status === 'processing') return 'warn';
  return 'info';
}

function EmptyState({ title, body, action }) {
  return <div className="emptyState">
    <div className="emptyOrb">∅</div>
    <h3>{title}</h3>
    <p>{body}</p>
    {action}
  </div>;
}

function MetricCard({ label, value, sub, tone = 'blue' }) {
  return <div className={`metricCard tone-${tone}`}>
    <span>{label}</span>
    <strong>{value}</strong>
    {sub ? <small>{sub}</small> : null}
  </div>;
}

function Toasts({ messages }) {
  return <div className="toastStack">
    {messages.slice(-4).map((m) => <div key={m.id} className={`toast ${m.kind || 'info'}`}>{m.text}</div>)}
  </div>;
}

function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [apiStatus, setApiStatus] = useState('checking');
  const [runs, setRuns] = useState([]);
  const [profiles, setProfiles] = useState(['default']);
  const [run, setRun] = useState(null);
  const [runDetail, setRunDetail] = useState(null);
  const [items, setItems] = useState([]);
  const [selectedItemId, setSelectedItemId] = useState('');
  const [selectedItemDetail, setSelectedItemDetail] = useState(null);
  const [media, setMedia] = useState([]);
  const [files, setFiles] = useState([]);
  const [provider, setProvider] = useState('mock');
  const [profileName, setProfileName] = useState('default');
  const [mediaType, setMediaType] = useState('photos');
  const [manualItem, setManualItem] = useState({...DEFAULT_ITEM, final_name: 'RAGU Projector', visible_condition: 'Used', notes: 'Similar model, tested working, no remote'});
  const [evidence, setEvidence] = useState({...DEFAULT_EVIDENCE, url_platform: 'ebay', price: '32', listing_type: 'sold', notes: 'Previously sold online comp'});
  const [screenshotEvidence, setScreenshotEvidence] = useState({ file: null, listing_type: 'sold', platform: 'ebay', notes: '', ocr_text: '' });
  const [exports, setExports] = useState([]);
  const [busy, setBusy] = useState(false);
  const [messages, setMessages] = useState([]);
  const [search, setSearch] = useState('');
  const dropRef = useRef(null);

  const activeRunId = run?.run_id;
  const selectedItem = useMemo(() => items.find(i => i.item_id === selectedItemId) || null, [items, selectedItemId]);

  const stats = useMemo(() => {
    const total = items.length;
    const verified = items.filter(i => i.confidence === 'Verified').length;
    const inferred = items.filter(i => i.confidence === 'Inferred').length;
    const unknown = items.filter(i => i.confidence === 'Unknown').length;
    const priced = items.filter(i => i.value_export !== null && i.value_export !== undefined).length;
    const exportValue = items.reduce((sum, i) => sum + (Number(i.value_export) || 0), 0);
    const missingEvidence = items.filter(i => !i.valuation_passed_gates).length;
    return { total, verified, inferred, unknown, priced, exportValue, missingEvidence };
  }, [items]);

  function notify(text, kind = 'info') {
    const id = `${Date.now()}_${Math.random().toString(16).slice(2)}`;
    setMessages(prev => [...prev, { id, text, kind }]);
    setTimeout(() => setMessages(prev => prev.filter(m => m.id !== id)), 5200);
  }

  async function safe(label, fn, success) {
    setBusy(true);
    try {
      const result = await fn();
      if (success) notify(success(result), 'good');
      return result;
    } catch (err) {
      notify(`${label} failed: ${err.message}`, 'danger');
      throw err;
    } finally {
      setBusy(false);
    }
  }

  async function bootstrap() {
    try {
      await SimLayApi.health();
      setApiStatus('online');
      const [runData, profileData] = await Promise.all([SimLayApi.listRuns(), SimLayApi.listProfiles().catch(() => ({profiles:['default']}))]);
      setRuns(runData.runs || []);
      setProfiles(profileData.profiles || ['default']);
      if (!run && (runData.runs || []).length) await selectRun(runData.runs[0]);
    } catch (err) {
      setApiStatus('offline');
      notify('Backend is offline. Start backend from START_APP_WINDOWS.ps1 or run uvicorn manually.', 'danger');
    }
  }

  useEffect(() => { bootstrap(); }, []);
  useEffect(() => {
    if (selectedItemId) {
      SimLayApi.getItem(selectedItemId).then(setSelectedItemDetail).catch(() => setSelectedItemDetail(null));
    } else {
      setSelectedItemDetail(null);
    }
  }, [selectedItemId]);

  async function refreshRuns() {
    const data = await SimLayApi.listRuns();
    setRuns(data.runs || []);
  }

  async function loadRunSideData(runId) {
    const [itemData, mediaData, detail] = await Promise.all([
      SimLayApi.listItems(runId),
      SimLayApi.listMedia(runId).catch(() => ({media: []})),
      SimLayApi.getRun(runId).catch(() => null),
    ]);
    setItems(itemData.items || []);
    setMedia(mediaData.media || []);
    setRunDetail(detail);
    if ((itemData.items || []).length && !selectedItemId) {
      setSelectedItemId(itemData.items[0].item_id);
      setEvidence(prev => ({...prev, item_id: itemData.items[0].item_id}));
    }
  }

  async function selectRun(r) {
    setRun(r);
    await loadRunSideData(r.run_id);
  }

  async function createRun() {
    await safe('Create run', async () => {
      const created = await SimLayApi.createRun({ profile_name: profileName, media_type: mediaType });
      setRun(created);
      await refreshRuns();
      await loadRunSideData(created.run_id);
      setActiveTab('intake');
      return created;
    }, r => `Run ${r.run_short} created`);
  }

  function handleFiles(nextFiles) {
    const arr = [...nextFiles];
    setFiles(arr);
    notify(`${arr.length} file${arr.length === 1 ? '' : 's'} staged for upload`, 'info');
  }

  async function uploadMedia() {
    if (!activeRunId) return notify('Create or select a run first.', 'warn');
    if (!files.length) return notify('Choose photos or a video first.', 'warn');
    await safe('Upload media', async () => {
      const result = await SimLayApi.uploadMedia(activeRunId, files);
      await loadRunSideData(activeRunId);
      return result;
    }, r => `${r.uploaded?.length || 0} media records added`);
  }

  async function processMedia() {
    if (!activeRunId) return notify('Create or select a run first.', 'warn');
    await safe('Process media', async () => {
      const result = await SimLayApi.processRun(activeRunId, provider);
      await loadRunSideData(activeRunId);
      setActiveTab('review');
      return result;
    }, r => `${r.items_created ?? 'Vision'} item detections processed`);
  }

  async function addManualItem() {
    if (!activeRunId) return notify('Create or select a run first.', 'warn');
    if (!manualItem.final_name.trim()) return notify('Item name is required.', 'warn');
    await safe('Add item', async () => {
      const payload = { ...manualItem, run_id: activeRunId, quantity: Number(manualItem.quantity) || 1 };
      const result = await SimLayApi.createItem(payload);
      await loadRunSideData(activeRunId);
      setSelectedItemId(result.item_id);
      setEvidence(prev => ({ ...prev, item_id: result.item_id }));
      return result;
    }, r => `Item added: ${r.item_id}`);
  }

  async function saveSelectedItem() {
    if (!selectedItem) return notify('Select an item first.', 'warn');
    await safe('Update item', async () => {
      await SimLayApi.updateItem(selectedItem.item_id, {
        final_name: selectedItem.final_name,
        brand: selectedItem.brand,
        category: selectedItem.category,
        quantity: selectedItem.quantity,
        visible_condition: selectedItem.visible_condition,
        confidence: selectedItem.confidence,
        confidence_reason: selectedItem.confidence_reason,
        notes: selectedItem.notes,
      });
      await loadRunSideData(activeRunId);
      return true;
    }, () => 'Item saved');
  }

  function patchSelectedItem(update) {
    if (!selectedItem) return;
    setItems(prev => prev.map(i => i.item_id === selectedItem.item_id ? { ...i, ...update } : i));
  }

  async function addEvidence() {
    if (!evidence.item_id) return notify('Select an item for evidence.', 'warn');
    await safe('Add evidence', async () => {
      const payload = { ...evidence, price: evidence.price ? Number(evidence.price) : null };
      const result = await SimLayApi.addEvidence(payload);
      await loadRunSideData(activeRunId);
      setSelectedItemId(evidence.item_id);
      return result;
    }, () => 'Evidence saved and valuation recalculated');
  }

  async function addScreenshotEvidence() {
    if (!selectedItemId) return notify('Select an item first.', 'warn');
    if (!screenshotEvidence.file) return notify('Choose screenshot evidence first.', 'warn');
    await safe('Add screenshot evidence', async () => {
      const result = await SimLayApi.addScreenshotEvidence({ item_id: selectedItemId, ...screenshotEvidence });
      await loadRunSideData(activeRunId);
      return result;
    }, () => 'Screenshot evidence stored');
  }

  async function refreshUrls() {
    if (!activeRunId) return notify('Select a run first.', 'warn');
    await safe('Refresh URLs', async () => {
      const result = await SimLayApi.refreshRunEvidence(activeRunId);
      await loadRunSideData(activeRunId);
      return result;
    }, r => `${r.refreshed?.length || 0} evidence URLs checked`);
  }

  async function exportCsv() {
    if (!activeRunId) return notify('Select a run first.', 'warn');
    await safe('Export CSV', async () => {
      const result = await SimLayApi.exportCsv(activeRunId);
      setExports(prev => [{ type: 'Wix CSV', ...result }, ...prev]);
      return result;
    }, r => `Wix CSV ready: ${r.row_count} product rows`);
  }

  async function exportAudit() {
    if (!activeRunId) return notify('Select a run first.', 'warn');
    await safe('Export audit', async () => {
      const result = await SimLayApi.exportAudit(activeRunId);
      setExports(prev => [{ type: 'Audit JSON', ...result }, ...prev]);
      return result;
    }, () => 'Audit JSON ready');
  }

  const filteredItems = items.filter(i => {
    const text = `${i.final_name || ''} ${i.brand || ''} ${i.category || ''} ${i.notes || ''}`.toLowerCase();
    return text.includes(search.toLowerCase());
  });

  return <main className="appFrame">
    <aside className="sidebar">
      <div className="brandBlock">
        <div className="brandMark">FT</div>
        <div>
          <b>StorageUnit</b>
          <span>SimLay Pro</span>
        </div>
      </div>
      <nav>
        {tabs.map(t => <button key={t.id} className={activeTab === t.id ? 'active' : ''} onClick={() => setActiveTab(t.id)}><i>{t.icon}</i>{t.label}</button>)}
      </nav>
      <div className="sidePanel">
        <span>Backend</span>
        <strong className={`pill ${apiStatus === 'online' ? 'good' : apiStatus === 'offline' ? 'danger' : 'warn'}`}>{apiStatus}</strong>
      </div>
      <div className="sidePanel small">
        <span>Active Run</span>
        <strong>{run?.run_short || 'None'}</strong>
      </div>
    </aside>

    <section className="workspace">
      <header className="topbar">
        <div>
          <p className="eyebrow">Accuracy-first resale intelligence</p>
          <h1>{activeTab === 'dashboard' ? 'FalseTech Command Center' : tabs.find(t => t.id === activeTab)?.label}</h1>
        </div>
        <div className="topActions">
          <button className="ghostButton" onClick={bootstrap}>Refresh</button>
          <button className="primaryButton" onClick={createRun} disabled={busy}>New Run</button>
        </div>
      </header>

      {activeTab === 'dashboard' && <section className="pageGrid dashboardGrid">
        <div className="heroCard wide">
          <div className="heroCopy">
            <p className="eyebrow">Photos / video → verified inventory → evidence-gated pricing → Wix CSV</p>
            <h2>Built for storage-unit flips where every price needs a reason.</h2>
            <p>No silent guessing. Unknown stays unknown. Prices export only when the evidence gates pass.</p>
            <div className="heroActions">
              <button className="primaryButton" onClick={() => setActiveTab('intake')}>Start Intake</button>
              <button className="ghostButton" onClick={() => setActiveTab('export')}>Open Export Center</button>
            </div>
          </div>
          <div className="pipelineVisual">
            {['Ingest', 'Detect', 'Dedupe', 'Evidence', 'Value', 'Export'].map((x, idx) => <div key={x}><b>{idx + 1}</b><span>{x}</span></div>)}
          </div>
        </div>
        <MetricCard label="Items" value={stats.total} sub={`${stats.verified} verified / ${stats.unknown} unknown`} tone="blue" />
        <MetricCard label="Priced" value={stats.priced} sub="passed valuation gates" tone="green" />
        <MetricCard label="Export Value" value={money(stats.exportValue)} sub="conservative export total" tone="purple" />
        <MetricCard label="Needs Evidence" value={stats.missingEvidence} sub="missing comps or failed gates" tone="orange" />

        <div className="panel wide">
          <div className="panelHeader"><h2>Runs</h2><button className="ghostButton" onClick={refreshRuns}>Reload</button></div>
          <div className="runList">
            {runs.length ? runs.map(r => <button key={r.run_id} className={`runCard ${run?.run_id === r.run_id ? 'selected' : ''}`} onClick={() => selectRun(r)}>
              <span>{r.run_short}</span><b>{r.total_items || 0} items</b><small>{r.profile_name} · <em className={`pill ${classForStatus(r.status)}`}>{r.status}</em></small>
            </button>) : <EmptyState title="No runs yet" body="Create a run to begin inventory intake." action={<button className="primaryButton" onClick={createRun}>Create First Run</button>} />}
          </div>
        </div>

        <div className="panel">
          <h2>Truth Gates</h2>
          <ul className="checkList">
            <li>Confidence required</li><li>Condition is visual-only</li><li>Prices need evidence</li><li>Wix headers strict</li><li>Audit JSON available</li>
          </ul>
        </div>

        <InventoryPanel runId={run?.run_id} />
      </section>}

      {activeTab === 'intake' && <section className="pageGrid intakeGrid">
        <div className="panel">
          <div className="panelHeader"><h2>Create / Select Run</h2><span className="pill info">Profile-driven</span></div>
          <label>Project Profile<select value={profileName} onChange={e => setProfileName(e.target.value)}>{profiles.map(p => <option key={p}>{p}</option>)}</select></label>
          <label>Media Type<select value={mediaType} onChange={e => setMediaType(e.target.value)}><option value="photos">Photos</option><option value="video">Video</option></select></label>
          <button className="primaryButton" onClick={createRun} disabled={busy}>Create Run</button>
        </div>

        <div className="panel wide">
          <div className="panelHeader"><h2>Media Intake</h2><span>{media.length} stored media</span></div>
          <div ref={dropRef} className="dropZone" onDragOver={e => e.preventDefault()} onDrop={e => { e.preventDefault(); handleFiles(e.dataTransfer.files); }}>
            <div className="uploadIcon">▧</div>
            <h3>Drop storage-unit photos or walkthrough video</h3>
            <p>Photo batches stay unordered. Video files create capped keyframes using the backend config.</p>
            <input type="file" multiple accept="image/*,video/*" onChange={e => handleFiles(e.target.files)} />
          </div>
          <div className="fileStrip">{files.length ? files.map(f => <span key={`${f.name}_${f.size}`}>{f.name}</span>) : <span>No files staged</span>}</div>
          <div className="buttonRow"><button className="primaryButton" onClick={uploadMedia} disabled={busy || !activeRunId}>Upload Media</button><select value={provider} onChange={e => setProvider(e.target.value)}><option value="mock">Mock Vision</option><option value="openai">OpenAI Vision</option></select><button className="successButton" onClick={processMedia} disabled={busy || !activeRunId}>Process Run</button></div>
        </div>

        <div className="panel wide">
          <div className="panelHeader"><h2>Manual Item Capture</h2><span className="pill warn">Fallback-safe</span></div>
          <div className="formGrid">
            <label>Item Name<input value={manualItem.final_name} onChange={e => setManualItem({...manualItem, final_name:e.target.value})} placeholder="RAGU Projector" /></label>
            <label>Brand<input value={manualItem.brand} onChange={e => setManualItem({...manualItem, brand:e.target.value})} placeholder="Only if visible/known" /></label>
            <label>Category<input value={manualItem.category} onChange={e => setManualItem({...manualItem, category:e.target.value})} placeholder="Electronics, Tools, Furniture" /></label>
            <label>Condition<select value={manualItem.visible_condition} onChange={e => setManualItem({...manualItem, visible_condition:e.target.value})}>{['New','Like New','Used','Fair','Parts','Unknown'].map(x => <option key={x}>{x}</option>)}</select></label>
            <label>Confidence<select value={manualItem.confidence} onChange={e => setManualItem({...manualItem, confidence:e.target.value})}>{['Verified','Inferred','Unknown'].map(x => <option key={x}>{x}</option>)}</select></label>
            <label>Quantity<input type="number" min="1" value={manualItem.quantity} onChange={e => setManualItem({...manualItem, quantity:e.target.value})} /></label>
          </div>
          <label>Notes<textarea value={manualItem.notes} onChange={e => setManualItem({...manualItem, notes:e.target.value})} placeholder="Testing, missing remote, visible damage, accessories..." /></label>
          <button className="primaryButton" onClick={addManualItem} disabled={busy || !activeRunId}>Add Manual Item</button>
        </div>
      </section>}

      {activeTab === 'review' && <section className="pageGrid reviewGrid">
        <div className="panel wide">
          <div className="panelHeader"><h2>Inventory Review</h2><input className="search" placeholder="Search inventory" value={search} onChange={e => setSearch(e.target.value)} /></div>
          {filteredItems.length ? <div className="inventoryGrid">{filteredItems.map(i => <button key={i.item_id} className={`itemCard ${selectedItemId === i.item_id ? 'selected' : ''}`} onClick={() => { setSelectedItemId(i.item_id); setEvidence(prev => ({...prev, item_id:i.item_id})); }}>
            <div className="itemCardTop"><strong>{i.final_name}</strong><span className={`pill ${classForConfidence(i.confidence)}`}>{i.confidence}</span></div>
            <p>{i.category || 'Uncategorized'} · {i.visible_condition || 'Unknown'}</p>
            <div className="valueRow"><span>p25 {money(i.value_p25)}</span><b>Export {money(i.value_export)}</b></div>
            <div className="flagRow">{i.valuation_passed_gates ? <span className="pill good">gates passed</span> : <span className="pill warn">needs evidence</span>}{i.flag_duplicate_suspect ? <span className="pill danger">duplicate?</span> : null}</div>
          </button>)}</div> : <EmptyState title="No inventory yet" body="Upload photos and process with vision, or add a manual item." action={<button className="primaryButton" onClick={() => setActiveTab('intake')}>Go to Intake</button>} />}
        </div>
        <div className="panel detailPanel">
          <div className="panelHeader"><h2>Selected Item</h2>{selectedItem ? <span className="pill info">{selectedItem.sort_tier ? `Tier ${selectedItem.sort_tier}` : 'Review'}</span> : null}</div>
          {selectedItem ? <>
            <label>Name<input value={selectedItem.final_name || ''} onChange={e => patchSelectedItem({final_name:e.target.value})} /></label>
            <label>Brand<input value={selectedItem.brand || ''} onChange={e => patchSelectedItem({brand:e.target.value})} /></label>
            <div className="formGrid compact">
              <label>Condition<select value={selectedItem.visible_condition || 'Unknown'} onChange={e => patchSelectedItem({visible_condition:e.target.value})}>{['New','Like New','Used','Fair','Parts','Unknown'].map(x => <option key={x}>{x}</option>)}</select></label>
              <label>Confidence<select value={selectedItem.confidence || 'Inferred'} onChange={e => patchSelectedItem({confidence:e.target.value})}>{['Verified','Inferred','Unknown'].map(x => <option key={x}>{x}</option>)}</select></label>
            </div>
            <label>Notes<textarea value={selectedItem.notes || ''} onChange={e => patchSelectedItem({notes:e.target.value})} /></label>
            <div className="miniEvidence"><h3>Evidence Records</h3>{selectedItemDetail?.evidence?.length ? selectedItemDetail.evidence.map(ev => <div className="evidenceLine" key={ev.evidence_id}><span>{ev.listing_type} · {ev.url_platform || ev.source_type}</span><b>{money(ev.price)}</b></div>) : <p className="muted">No evidence yet.</p>}</div>
            <button className="primaryButton" onClick={saveSelectedItem}>Save Changes</button>
          </> : <EmptyState title="Select an item" body="Choose an inventory card to inspect/edit it." />}
        </div>
      </section>}

      {activeTab === 'evidence' && <section className="pageGrid evidenceGrid">
        <div className="panel">
          <div className="panelHeader"><h2>Evidence Target</h2><span className="pill info">{selectedItem?.final_name || 'None'}</span></div>
          <label>Item<select value={evidence.item_id || selectedItemId} onChange={e => { setEvidence({...evidence, item_id:e.target.value}); setSelectedItemId(e.target.value); }}><option value="">Select item</option>{items.map(i => <option key={i.item_id} value={i.item_id}>{i.final_name}</option>)}</select></label>
          {selectedItem ? <div className="decisionCard"><span>Current AI export value</span><strong>{money(selectedItem.value_export)}</strong><small>{selectedItem.valuation_passed_gates ? 'Evidence gates passed' : 'Price blocked until gates pass'}</small></div> : null}
        </div>
        <div className="panel">
          <h2>Structured URL Evidence</h2>
          <label>URL<input placeholder="Paste sold or active listing URL" value={evidence.url} onChange={e => setEvidence({...evidence, url:e.target.value})} /></label>
          <div className="formGrid compact">
            <label>Platform<input value={evidence.url_platform} onChange={e => setEvidence({...evidence, url_platform:e.target.value})} placeholder="ebay" /></label>
            <label>Type<select value={evidence.listing_type} onChange={e => setEvidence({...evidence, listing_type:e.target.value})}><option value="sold">Sold</option><option value="active">Active</option><option value="auction_ended">Auction Ended</option></select></label>
            <label>Price<input value={evidence.price} onChange={e => setEvidence({...evidence, price:e.target.value})} placeholder="32" /></label>
            <label>Sale Date<input type="date" value={evidence.sale_date} onChange={e => setEvidence({...evidence, sale_date:e.target.value})} /></label>
          </div>
          <label>Notes<textarea value={evidence.notes} onChange={e => setEvidence({...evidence, notes:e.target.value})} /></label>
          <div className="buttonRow"><button className="primaryButton" onClick={addEvidence}>Add Evidence</button><button className="ghostButton" onClick={refreshUrls}>Refresh URLs</button></div>
        </div>
        <div className="panel wide">
          <h2>Screenshot Evidence Parser</h2>
          <div className="formGrid">
            <label>Screenshot<input type="file" accept="image/*" onChange={e => setScreenshotEvidence({...screenshotEvidence, file:e.target.files?.[0] || null})} /></label>
            <label>Platform<input value={screenshotEvidence.platform} onChange={e => setScreenshotEvidence({...screenshotEvidence, platform:e.target.value})} /></label>
            <label>Type<select value={screenshotEvidence.listing_type} onChange={e => setScreenshotEvidence({...screenshotEvidence, listing_type:e.target.value})}><option value="sold">Sold</option><option value="active">Active</option><option value="auction_ended">Auction Ended</option></select></label>
          </div>
          <label>Optional OCR Text / Manual Extraction Paste<textarea value={screenshotEvidence.ocr_text} onChange={e => setScreenshotEvidence({...screenshotEvidence, ocr_text:e.target.value})} placeholder="Paste text from screenshot here if OCR is unavailable..." /></label>
          <label>Notes<textarea value={screenshotEvidence.notes} onChange={e => setScreenshotEvidence({...screenshotEvidence, notes:e.target.value})} /></label>
          <button className="primaryButton" onClick={addScreenshotEvidence}>Parse + Save Screenshot Evidence</button>
        </div>
      </section>}

      {activeTab === 'export' && <section className="pageGrid exportGrid">
        <div className="heroCard wide exportHero">
          <div><p className="eyebrow">Wix-ready output</p><h2>Export only product rows with strict template headers.</h2><p>Unused Wix columns stay present and blank. Prices export only when valuation gates allow them.</p></div>
          <div className="exportButtons"><button className="primaryButton" onClick={exportCsv}>Generate Wix CSV</button><button className="ghostButton" onClick={exportAudit}>Generate Audit JSON</button></div>
        </div>
        <MetricCard label="Rows" value={stats.total} sub="one PRODUCT row per item" tone="blue" />
        <MetricCard label="Exported Price Total" value={money(stats.exportValue)} sub="blank values excluded" tone="green" />
        <MetricCard label="Blocked Prices" value={stats.total - stats.priced} sub="failed or missing evidence" tone="orange" />
        <div className="panel wide"><h2>Downloads</h2>{exports.length ? <div className="downloadList">{exports.map((ex, idx) => <a key={`${ex.export_id}_${idx}`} href={downloadUrl(ex.export_id)} target="_blank" rel="noreferrer"><span>{ex.type}</span><b>{ex.export_id}</b><small>{ex.validation_passed === false ? 'validation failed' : 'ready'}</small></a>)}</div> : <EmptyState title="No exports yet" body="Generate a Wix CSV or audit JSON to get download links." />}</div>
      </section>}

      {activeTab === 'settings' && <section className="pageGrid">
        <div className="panel wide">
          <h2>Deployment Checklist</h2>
          <div className="deployGrid">
            <div><b>1. Backend</b><code>python -m uvicorn app.main:app --reload</code></div>
            <div><b>2. Frontend</b><code>npm run dev</code></div>
            <div><b>3. OpenAI Vision</b><code>OPENAI_API_KEY required</code></div>
            <div><b>4. Wix Export</b><code>Strict header match enabled</code></div>
          </div>
        </div>
        <div className="panel">
          <h2>Connector Status</h2>
          <button className="ghostButton" onClick={() => SimLayApi.ebayStatus().then(s => notify(`eBay: ${s.configured ? 'configured' : s.reason}`, s.configured ? 'good' : 'warn')).catch(e => notify(e.message, 'danger'))}>Check eBay API</button>
          <p className="muted">Connectors fail closed. No coverage is claimed until credentials and approved access are present.</p>
        </div>
        <div className="panel">
          <h2>Current Run Snapshot</h2>
          <pre>{JSON.stringify({ run: runDetail || run, stats }, null, 2)}</pre>
        </div>
      </section>}
    </section>
    {busy ? <div className="busyOverlay"><div className="spinner"></div><b>Working...</b></div> : null}
    <Toasts messages={messages} />
  </main>;
}

createRoot(document.getElementById('root')).render(<App />);
