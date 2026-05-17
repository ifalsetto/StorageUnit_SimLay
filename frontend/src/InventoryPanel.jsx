import { useEffect, useMemo, useState } from "react";
import { listItems, listMedia, mediaUrl } from "./api";

function getItemImage(item, mediaList) {
  if (!item || !Array.isArray(mediaList)) return "";

  const mediaId =
    item.representative_image_id ||
    item.representative_image_ref ||
    item.media_id;

  const matched = mediaList.find((m) => {
    return (
      m.media_id === mediaId ||
      m.id === mediaId ||
      item.file_path === m.file_path
    );
  });

  if (matched?.file_path) {
    return mediaUrl(matched.file_path);
  }

  const firstPhoto = mediaList.find((m) => {
    return String(m.file_type || "").toLowerCase() === "photo";
  });

  return firstPhoto?.file_path ? mediaUrl(firstPhoto.file_path) : "";
}

export default function InventoryPanel({ runId }) {
  const [items, setItems] = useState([]);
  const [media, setMedia] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function refreshInventory() {
    if (!runId) return;

    setLoading(true);
    setError("");

    try {
      const [itemData, mediaData] = await Promise.all([
        listItems(runId),
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
    refreshInventory();
  }, [runId]);

  const sortedItems = useMemo(() => {
    return [...items].sort((a, b) => {
      const tierA = Number(a.sort_tier || 99);
      const tierB = Number(b.sort_tier || 99);

      if (tierA !== tierB) return tierA - tierB;

      return String(a.final_name || a.raw_name || "").localeCompare(
        String(b.final_name || b.raw_name || "")
      );
    });
  }, [items]);

  return (
    <section className="inventory-panel">
      <div className="section-header">
        <div>
          <p className="eyebrow">Current Inventory</p>
          <h2>Items in This Run</h2>
        </div>

        <button className="secondary-button" onClick={refreshInventory}>
          {loading ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      {!runId && (
        <div className="empty-state">
          Create or select a run to view inventory.
        </div>
      )}

      {error && <div className="error-box">{error}</div>}

      {runId && !loading && sortedItems.length === 0 && (
        <div className="empty-state">
          No inventory items yet. Upload media, then run mock vision or add items manually.
        </div>
      )}

      <div className="inventory-list">
        {sortedItems.map((item) => {
          const img = getItemImage(item, media);

          return (
            <article className="inventory-row" key={item.item_id || item.id}>
              <div className="inventory-thumb-wrap">
                {img ? (
                  <img
                    className="inventory-thumb"
                    src={img}
                    alt={item.final_name || item.raw_name || "Inventory item"}
                    loading="lazy"
                  />
                ) : (
                  <div className="inventory-thumb placeholder">No Photo</div>
                )}
              </div>

              <div className="inventory-main">
                <div className="inventory-title-line">
                  <h3>{item.final_name || item.raw_name || "Unnamed Item"}</h3>
                  <span className={`status-pill ${String(item.confidence || "unknown").toLowerCase()}`}>
                    {item.confidence || "Unknown"}
                  </span>
                </div>

                <div className="inventory-meta">
                  <span>{item.category || "Uncategorized"}</span>
                  <span>{item.visible_condition || "Unknown condition"}</span>
                  <span>{item.source || "Unknown source"}</span>
                </div>

                {item.notes && <p className="inventory-notes">{item.notes}</p>}
              </div>

              <div className="inventory-price">
                {item.value_export ? (
                  <>
                    <span className="price-label">Export Price</span>
                    <strong>${Number(item.value_export).toFixed(0)}</strong>
                  </>
                ) : (
                  <>
                    <span className="price-label">Price</span>
                    <strong>Blank</strong>
                  </>
                )}
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
