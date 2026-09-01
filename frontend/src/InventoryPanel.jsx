import { useEffect, useMemo, useState } from "react";
import { SimLayApi, listItems, listMedia, mediaUrl } from "./api";
import "./styles/inventory-owner.css";

const OWNERS = ["All", "Thomas", "Mine", "Unassigned"];
const OWNER_VALUES = ["Thomas", "Mine", "Unassigned"];
const ACTIONS = ["All", "Sell", "Donate", "Dump", "Hold", "Unassigned"];
const ACTION_VALUES = ["Sell", "Donate", "Dump", "Hold", "Unassigned"];
const CONDITIONS = ["New", "Like New", "Used", "Fair", "Parts", "Unknown"];
const CONFIDENCE = ["Verified", "Inferred", "Unknown"];
const SOURCES = ["Photo", "User Confirmed", "User Visual", "Default Library", "Tony History", "Approved Comp", "Web (Cited)", "Manual"];

function parseMediaIds(item) {
  const ids = [];
  if (item?.representative_image_id) ids.push(item.representative_image_id);
  const raw = item?.detected_in_media;
  if (Array.isArray(raw)) {
    raw.forEach((id) => id && !ids.includes(id) && ids.push(id));
  } else if (typeof raw === "string" && raw.trim()) {
    try {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) parsed.forEach((id) => id && !ids.includes(id) && ids.push(id));
    } catch {
      // Legacy malformed media JSON: keep only the explicit representative image.
    }
  }
  return ids;
}

function getItemImage(item, mediaList) {
  for (const id of parseMediaIds(item)) {
    const matched = mediaList.find((m) => m.media_id === id || m.id === id);
    if (matched?.file_path) return mediaUrl(matched.file_path);
  }
  return "";
}

function numberOrNull(value) {
  if (value === "" || value === null || value === undefined) return null;
  const n = Number(value);
  return Number.isFinite(n) && n >= 0 ? n : null;
}

function makeDraft(item) {
  return {
    final_name: item.final_name || "",
    owner: item.owner || "Unassigned",
    item_action: item.item_action || "Unassigned",
    category: item.category || "",
    visible_condition: item.visible_condition || "Unknown",
    confidence: item.confidence || "Unknown",
    source: item.source || "User Visual",
    manual_value_low: item.manual_value_low ?? item.value_p25 ?? "",
    manual_value_expected: item.manual_value_expected ?? item.value_p50 ?? item.value_export ?? "",
    manual_value_high: item.manual_value_high ?? item.value_p75 ?? "",
    asking_price: item.asking_price ?? "",
    notes: item.notes || "",
  };
}

function money(value) {
  const n = Number(value);
  return Number.isFinite(n) ? `$${n.toFixed(n % 1 === 0 ? 0 : 2)}` : "—";
}

export default function InventoryPanel({ runId }) {
  const [items, setItems] = useState([]);
  const [media, setMedia] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [ownerFilter, setOwnerFilter] = useState("All");
  const [actionFilter, setActionFilter] = useState("All");
  const [search, setSearch] = useState("");
  const [showTrash, setShowTrash] = useState(false);
  const [editingId, setEditingId] = useState("");
  const [draft, setDraft] = useState(null);
  const [deleteId, setDeleteId] = useState("");
  const [busyId, setBusyId] = useState("");

  async function refreshInventory() {
    if (!runId) return;
    setLoading(true);
    setError("");
    try {
      const [itemData, mediaData] = await Promise.all([
        listItems(runId, { includeDeleted: showTrash }),
        listMedia(runId),
      ]);
      setItems(itemData.items || itemData.inventory || []);
      setMedia(mediaData.media || []);
    } catch (err) {
      setError(err.message || "Failed to load inventory");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    setEditingId("");
    setDraft(null);
    setDeleteId("");
    refreshInventory();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId, showTrash]);

  const filteredItems = useMemo(() => {
    const q = search.trim().toLowerCase();
    return [...items]
      .filter((item) => (showTrash ? Boolean(item.deleted_at) : !item.deleted_at))
      .filter((item) => ownerFilter === "All" || (item.owner || "Unassigned") === ownerFilter)
      .filter((item) => actionFilter === "All" || (item.item_action || "Unassigned") === actionFilter)
      .filter((item) => !q || [item.final_name, item.raw_name, item.brand, item.category, item.notes, item.item_id]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(q)))
      .sort((a, b) => {
        const tierA = Number(a.sort_tier || 99);
        const tierB = Number(b.sort_tier || 99);
        if (tierA !== tierB) return tierA - tierB;
        return String(a.final_name || "").localeCompare(String(b.final_name || ""));
      });
  }, [items, ownerFilter, actionFilter, search, showTrash]);

  const metrics = useMemo(() => {
    let low = 0, expected = 0, high = 0, asking = 0;
    filteredItems.forEach((item) => {
      low += Number(item.display_value_low ?? item.manual_value_low ?? item.value_p25 ?? 0) || 0;
      expected += Number(item.display_value_expected ?? item.manual_value_expected ?? item.value_p50 ?? item.value_export ?? 0) || 0;
      high += Number(item.display_value_high ?? item.manual_value_high ?? item.value_p75 ?? 0) || 0;
      asking += Number(item.asking_price ?? 0) || 0;
    });
    return { count: filteredItems.length, low, expected, high, asking };
  }, [filteredItems]);

  function beginEdit(item) {
    setDeleteId("");
    setEditingId(item.item_id);
    setDraft(makeDraft(item));
  }

  async function saveEdit(itemId) {
    if (!draft) return;
    setBusyId(itemId);
    setError("");
    try {
      const low = numberOrNull(draft.manual_value_low);
      const expected = numberOrNull(draft.manual_value_expected);
      const high = numberOrNull(draft.manual_value_high);
      if (low !== null && high !== null && high < low) throw new Error("High value cannot be below low value.");
      if (expected !== null && low !== null && expected < low) throw new Error("Expected value cannot be below low value.");
      if (expected !== null && high !== null && expected > high) throw new Error("Expected value cannot be above high value.");
      await SimLayApi.updateItem(itemId, {
        final_name: draft.final_name,
        owner: draft.owner,
        item_action: draft.item_action,
        category: draft.category || null,
        visible_condition: draft.visible_condition,
        confidence: draft.confidence,
        source: draft.source,
        manual_value_low: low,
        manual_value_expected: expected,
        manual_value_high: high,
        asking_price: numberOrNull(draft.asking_price),
        notes: draft.notes || null,
      });
      setNotice("Saved.");
      setEditingId("");
      setDraft(null);
      await refreshInventory();
    } catch (err) {
      setError(err.message || "Failed to save item");
    } finally {
      setBusyId("");
    }
  }

  async function quickOwner(item, owner) {
    setBusyId(item.item_id);
    setError("");
    try {
      await SimLayApi.updateItem(item.item_id, { owner });
      setItems((current) => current.map((row) => row.item_id === item.item_id ? { ...row, owner } : row));
      setNotice(`Moved to ${owner}.`);
    } catch (err) {
      setError(err.message || "Failed to change owner");
    } finally {
      setBusyId("");
    }
  }

  async function confirmDelete(item) {
    setBusyId(item.item_id);
    setError("");
    try {
      await SimLayApi.deleteItem(item.item_id, "Deleted from owner inventory dashboard");
      setDeleteId("");
      setNotice("Moved to recoverable trash.");
      await refreshInventory();
    } catch (err) {
      setError(err.message || "Failed to delete item");
    } finally {
      setBusyId("");
    }
  }

  async function restoreItem(item) {
    setBusyId(item.item_id);
    try {
      await SimLayApi.restoreItem(item.item_id);
      setNotice("Restored.");
      await refreshInventory();
    } catch (err) {
      setError(err.message || "Failed to restore item");
    } finally {
      setBusyId("");
    }
  }

  async function duplicateItem(item) {
    setBusyId(item.item_id);
    try {
      await SimLayApi.duplicateItem(item.item_id, { owner: item.owner || "Unassigned" });
      setNotice("Duplicated. New copy is flagged for review.");
      await refreshInventory();
    } catch (err) {
      setError(err.message || "Failed to duplicate item");
    } finally {
      setBusyId("");
    }
  }

  return (
    <section className="owner-inventory-panel">
      <div className="section-header owner-inventory-header">
        <div>
          <p className="eyebrow">Owner-separated inventory</p>
          <h2>{showTrash ? "Recoverable Trash" : "Quick Inventory"}</h2>
          <p className="owner-subtitle">Thomas, Mine, and Unassigned stay explicit. Nothing is auto-reassigned.</p>
        </div>
        <div className="inventory-header-actions">
          <label className="trash-toggle"><input type="checkbox" checked={showTrash} onChange={(e) => setShowTrash(e.target.checked)} />Trash</label>
          <button className="secondary-button" type="button" onClick={refreshInventory} disabled={loading || !runId}>{loading ? "Refreshing..." : "Refresh"}</button>
        </div>
      </div>

      {!runId && <div className="empty-state">Create or select a run to manage inventory.</div>}
      {error && <div className="error-box">{error}</div>}
      {notice && <div className="inventory-notice" role="status">{notice}</div>}

      {runId && <>
        <div className="owner-toolbar">
          <div className="filter-group">{OWNERS.map((owner) => <button key={owner} type="button" className={ownerFilter === owner ? "filter-chip active" : "filter-chip"} onClick={() => setOwnerFilter(owner)}>{owner}</button>)}</div>
          <div className="filter-group action-filter">{ACTIONS.map((action) => <button key={action} type="button" className={actionFilter === action ? "filter-chip active" : "filter-chip"} onClick={() => setActionFilter(action)}>{action}</button>)}</div>
          <input className="inventory-search" type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search items..." aria-label="Search inventory" />
        </div>
        <div className="inventory-metrics">
          <div><span>Items</span><strong>{metrics.count}</strong></div>
          <div><span>Low</span><strong>{money(metrics.low)}</strong></div>
          <div><span>Expected</span><strong>{money(metrics.expected)}</strong></div>
          <div><span>High</span><strong>{money(metrics.high)}</strong></div>
          <div><span>Asking</span><strong>{money(metrics.asking)}</strong></div>
        </div>
      </>}

      {runId && !loading && filteredItems.length === 0 && <div className="empty-state">No items match this view.</div>}

      <div className="owner-inventory-list">
        {filteredItems.map((item) => {
          const img = getItemImage(item, media);
          const isEditing = editingId === item.item_id;
          const isDeleting = deleteId === item.item_id;
          const isBusy = busyId === item.item_id;
          return <article className={`owner-inventory-card ${item.deleted_at ? "is-deleted" : ""}`} key={item.item_id}>
            <div className="owner-thumb-wrap">{img ? <img className="owner-thumb" src={img} alt={item.final_name || "Inventory item"} loading="lazy" /> : <div className="owner-thumb placeholder">No linked photo</div>}</div>
            <div className="owner-card-main">
              <div className="owner-card-title-row">
                <div className="owner-card-title"><span className={`owner-badge owner-${String(item.owner || "Unassigned").toLowerCase()}`}>{item.owner || "Unassigned"}</span><h3>{item.final_name || item.raw_name || "Unnamed Item"}</h3></div>
                <span className={`status-pill ${String(item.confidence || "unknown").toLowerCase()}`}>{item.confidence || "Unknown"}</span>
              </div>

              {!isEditing && <>
                <div className="owner-meta"><span>{item.item_action || "Unassigned"}</span><span>{item.category || "Uncategorized"}</span><span>{item.visible_condition || "Unknown"}</span><span>{item.source || "Unknown source"}</span></div>
                <div className="owner-value-row"><span>{money(item.display_value_low)}–{money(item.display_value_high)}</span><strong>{money(item.asking_price ?? item.display_value_expected)}</strong></div>
                {item.notes && <p className="inventory-notes">{item.notes}</p>}
                {!item.deleted_at && <div className="owner-quick-row">
                  <label>Owner<select value={item.owner || "Unassigned"} disabled={isBusy} onChange={(e) => quickOwner(item, e.target.value)}>{OWNER_VALUES.map((owner) => <option key={owner}>{owner}</option>)}</select></label>
                  <div className="owner-card-actions">
                    <button type="button" className="secondary-button" onClick={() => beginEdit(item)}>Edit</button>
                    <button type="button" className="secondary-button" disabled={isBusy} onClick={() => duplicateItem(item)}>Duplicate</button>
                    {!isDeleting ? <button type="button" className="danger-button" onClick={() => setDeleteId(item.item_id)}>Delete</button> : <div className="delete-confirm"><span>Move to trash?</span><button type="button" className="danger-button" disabled={isBusy} onClick={() => confirmDelete(item)}>Confirm</button><button type="button" className="secondary-button" onClick={() => setDeleteId("")}>Cancel</button></div>}
                  </div>
                </div>}
                {item.deleted_at && <div className="owner-card-actions"><button type="button" className="secondary-button" disabled={isBusy} onClick={() => restoreItem(item)}>Restore</button><span className="deleted-note">Deleted {item.deleted_at}</span></div>}
              </>}

              {isEditing && draft && <div className="inventory-editor">
                <label className="wide">Name<input value={draft.final_name} onChange={(e) => setDraft({ ...draft, final_name: e.target.value })} /></label>
                <label>Owner<select value={draft.owner} onChange={(e) => setDraft({ ...draft, owner: e.target.value })}>{OWNER_VALUES.map((v) => <option key={v}>{v}</option>)}</select></label>
                <label>Action<select value={draft.item_action} onChange={(e) => setDraft({ ...draft, item_action: e.target.value })}>{ACTION_VALUES.map((v) => <option key={v}>{v}</option>)}</select></label>
                <label>Condition<select value={draft.visible_condition} onChange={(e) => setDraft({ ...draft, visible_condition: e.target.value })}>{CONDITIONS.map((v) => <option key={v}>{v}</option>)}</select></label>
                <label>Confidence<select value={draft.confidence} onChange={(e) => setDraft({ ...draft, confidence: e.target.value })}>{CONFIDENCE.map((v) => <option key={v}>{v}</option>)}</select></label>
                <label>Source<select value={draft.source} onChange={(e) => setDraft({ ...draft, source: e.target.value })}>{SOURCES.map((v) => <option key={v}>{v}</option>)}</select></label>
                <label>Category<input value={draft.category} onChange={(e) => setDraft({ ...draft, category: e.target.value })} /></label>
                <label>Low<input type="number" min="0" step="0.01" value={draft.manual_value_low} onChange={(e) => setDraft({ ...draft, manual_value_low: e.target.value })} /></label>
                <label>Expected<input type="number" min="0" step="0.01" value={draft.manual_value_expected} onChange={(e) => setDraft({ ...draft, manual_value_expected: e.target.value })} /></label>
                <label>High<input type="number" min="0" step="0.01" value={draft.manual_value_high} onChange={(e) => setDraft({ ...draft, manual_value_high: e.target.value })} /></label>
                <label>Asking<input type="number" min="0" step="0.01" value={draft.asking_price} onChange={(e) => setDraft({ ...draft, asking_price: e.target.value })} /></label>
                <label className="wide">Notes<textarea rows="3" value={draft.notes} onChange={(e) => setDraft({ ...draft, notes: e.target.value })} /></label>
                <div className="editor-actions wide"><button type="button" className="primary-button" disabled={isBusy || !draft.final_name.trim()} onClick={() => saveEdit(item.item_id)}>{isBusy ? "Saving..." : "Save"}</button><button type="button" className="secondary-button" onClick={() => { setEditingId(""); setDraft(null); }}>Cancel</button></div>
              </div>}
            </div>
          </article>;
        })}
      </div>
    </section>
  );
}
