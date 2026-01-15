import json
import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st


# ---------- Paths & setup ----------

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
UNITS_DIR = DATA_DIR / "units"
EXPORTS_DIR = BASE_DIR / "exports"
VALUE_LIBRARY_PATH = DATA_DIR / "value_library.json"
APPROVED_COMPS_PATH = DATA_DIR / "approved_comps.json"
SALES_HISTORY_PATH = DATA_DIR / "sales_history.csv"
AUDIT_LOG_PATH = DATA_DIR / "audit_log.jsonl"
UNITS_INDEX_PATH = DATA_DIR / "units_index.json"


def ensure_dirs():
    DATA_DIR.mkdir(exist_ok=True)
    UNITS_DIR.mkdir(exist_ok=True)
    EXPORTS_DIR.mkdir(exist_ok=True)
    if not UNITS_INDEX_PATH.exists():
        with open(UNITS_INDEX_PATH, "w", encoding="utf-8") as f:
            json.dump({"units": []}, f)


def log_audit(event: str, details: dict):
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "event": event,
        "details": details,
    }
    with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def load_units_index():
    ensure_dirs()
    if not UNITS_INDEX_PATH.exists():
        return {"units": []}
    # handle UTF-8 BOM from PowerShell-created file
    with open(UNITS_INDEX_PATH, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def save_units_index(index):
    with open(UNITS_INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)


def unit_path(unit_id: str) -> Path:
    return UNITS_DIR / f"{unit_id}.json"


def load_unit(unit_id: str) -> dict:
    path = unit_path(unit_id)
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_unit(unit_data: dict):
    path = unit_path(unit_data["unit_id"])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(unit_data, f, indent=2)


def safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


# ---------- JSON import helper ----------

def import_items_from_json(raw: str, phase: str):
    """
    Parse JSON from ChatGPT into normalized item dicts.
    raw: JSON string representing either a list of items or {"items": [...]}
    phase: "prepurchase" or "work"
    """
    raw = (raw or "").strip()
    if not raw:
        return []

    try:
        data = json.loads(raw)
    except Exception as e:
        raise ValueError(f"Invalid JSON: {e}")

    if isinstance(data, dict) and "items" in data:
        data = data["items"]

    if not isinstance(data, list):
        raise ValueError("JSON must be a list of items or an object with an 'items' list.")

    items = []
    for obj in data:
        name = (obj.get("name") or "").strip()
        if not name:
            continue

        item = {
            "id": str(uuid.uuid4()),
            "name": name,
            "category": (obj.get("category") or "unknown").strip(),
            "quantity": int(obj.get("quantity") or 1),
            "estimated_low": float(obj.get("estimated_low") or 0.0),
            "estimated_high": float(obj.get("estimated_high") or 0.0),
            "confidence": (obj.get("confidence") or "Unknown"),
            "source": (obj.get("source") or "Manual"),
            "platform": (obj.get("platform") or "Local marketplace").strip(),
            "status": (obj.get("status") or "Unassigned"),
            "notes": (obj.get("notes") or "").strip(),
            "phase": phase,
        }
        items.append(item)

    return items


# ---------- Summary / engine logic ----------

def compute_items_summary(items):
    total_low = 0.0
    total_high = 0.0
    for item in items:
        q = item.get("quantity", 1)
        v_low = safe_float(item.get("estimated_low"))
        v_high = safe_float(item.get("estimated_high"))
        total_low += v_low * q
        total_high += v_high * q
    total_expected = (total_low + total_high) / 2.0 if (total_low or total_high) else 0.0
    return total_low, total_high, total_expected


def compute_unit_overview(unit):
    """
    Dump fees are NOT included anymore. Only:
    - current_bid
    - other_costs
    """
    pre_items = unit.get("prepurchase_items", [])
    work_items = unit.get("work_items", [])
    items = work_items if work_items else pre_items

    low, high, expected = compute_items_summary(items)

    current_bid = safe_float(unit.get("current_bid"))
    dump_estimate = 0.0  # kept for compatibility but not used
    other_costs = safe_float(unit.get("other_costs"))
    total_costs = current_bid + other_costs
    expected_net = expected - total_costs

    return {
        "low_gross": low,
        "high_gross": high,
        "expected_gross": expected,
        "current_bid": current_bid,
        "dump_estimate": dump_estimate,
        "other_costs": other_costs,
        "total_costs": total_costs,
        "expected_net": expected_net,
    }


def unit_to_report_blocks(unit):
    overview = compute_unit_overview(unit)
    items = unit.get("work_items") or unit.get("prepurchase_items") or []

    # Decision summary
    decision_lines = []
    decision_lines.append(f"Unit ID: {unit['unit_id']}")
    decision_lines.append(f"Created: {unit.get('created_at', 'N/A')}")
    decision_lines.append(f"Status: {unit.get('status', 'unknown')}")
    decision_lines.append("")
    decision_lines.append("=== Decision Summary ===")
    decision_lines.append(f"Paid / Current Bid: ${overview['current_bid']:.2f}")
    decision_lines.append(f"Estimated Gross (Low): ${overview['low_gross']:.2f}")
    decision_lines.append(f"Estimated Gross (High): ${overview['high_gross']:.2f}")
    decision_lines.append(f"Expected Gross: ${overview['expected_gross']:.2f}")
    decision_lines.append(f"Other Costs: ${overview['other_costs']:.2f}")
    decision_lines.append(f"Total Costs: ${overview['total_costs']:.2f}")
    decision_lines.append(f"Expected Net: ${overview['expected_net']:.2f}")
    decision_summary = "\n".join(decision_lines)

    # Inventory list
    inv_lines = []
    inv_lines.append("=== Inventory ===")
    for item in items:
        inv_lines.append(
            f"- {item.get('name', 'Unnamed item')} "
            f"(qty {item.get('quantity', 1)}, "
            f"value ${safe_float(item.get('estimated_low')):.2f}–${safe_float(item.get('estimated_high')):.2f}, "
            f"confidence: {item.get('confidence', 'Unknown')}, "
            f"source: {item.get('source', 'Manual')}, "
            f"status: {item.get('status', 'Unassigned')})"
        )
    inventory_block = "\n".join(inv_lines)

    # Listing pack
    listing_lines = []
    listing_lines.append("=== Listing Pack (Sell Items Only) ===")
    for item in items:
        if item.get("status") == "Sell":
            name = item.get("name", "Unnamed item")
            qty = item.get("quantity", 1)
            platform = item.get("platform", "Local marketplace")
            v_low = safe_float(item.get("estimated_low"))
            v_high = safe_float(item.get("estimated_high"))
            listing_lines.append(f"{name} (x{qty})")
            listing_lines.append(f"Suggested platform: {platform}")
            listing_lines.append(f"Price band: ${v_low:.2f}–${v_high:.2f}")
            listing_lines.append("")
    listing_block = "\n".join(listing_lines)

    return decision_summary, inventory_block, listing_block


# ---------- UI helpers ----------

def select_or_create_unit():
    index = load_units_index()
    units = index.get("units", [])

    st.sidebar.header("Units")

    existing_ids = [u["unit_id"] for u in units]
    existing_labels = [f"{u['unit_id']} – {u.get('status', 'unknown')}" for u in units]

    selected_label = None
    if existing_labels:
        selected_label = st.sidebar.selectbox(
            "Open existing unit:",
            options=["(none)"] + existing_labels,
            index=0,
        )

    if selected_label and selected_label != "(none)":
        idx = existing_labels.index(selected_label)
        unit_id = existing_ids[idx]
        st.session_state["current_unit_id"] = unit_id

    st.sidebar.markdown("---")
    st.sidebar.subheader("Create new unit")

    if st.sidebar.button("Start new prospective unit"):
        unit_id = str(uuid.uuid4())[:8]
        created_at = datetime.utcnow().isoformat() + "Z"
        unit = {
            "unit_id": unit_id,
            "status": "prospective",
            "created_at": created_at,
            "purchased_at": None,
            "current_bid": 0.0,
            "dump_estimate": 0.0,
            "other_costs": 0.0,
            "prepurchase_items": [],
            "work_items": [],
            "closeout": {},
        }
        save_unit(unit)
        units.append({"unit_id": unit_id, "status": "prospective"})
        index["units"] = units
        save_units_index(index)
        log_audit("create_unit", {"unit_id": unit_id})
        st.session_state["current_unit_id"] = unit_id


def show_unit_header(unit):
    st.subheader(f"Unit ID: {unit['unit_id']}")
    st.write(f"Status: **{unit.get('status', 'unknown')}**")
    st.caption(f"Created at: {unit.get('created_at', 'N/A')} (UTC)")
    st.markdown("---")


# ---------- Pre-purchase UI ----------

def ui_prepurchase(unit, index):
    st.markdown("### Pre-Purchase Simulation (Before Buying)")

    # Only unit price + other costs matter now
    current_bid = st.number_input(
        "Current bid / expected price ($)",
        min_value=0.0,
        value=float(unit.get("current_bid") or 0.0),
        step=10.0,
    )
    other_costs = st.number_input(
        "Other costs (optional, e.g. gas, tips)",
        min_value=0.0,
        value=float(unit.get("other_costs") or 0.0),
        step=5.0,
    )

    unit["current_bid"] = current_bid
    unit["dump_estimate"] = 0.0
    unit["other_costs"] = other_costs
    save_unit(unit)

    st.markdown("#### Add item you can SEE in photos")

    with st.form("add_prepurchase_item"):
        name = st.text_input("Item name")
        category = st.text_input("Category", value="unknown")
        quantity = st.number_input("Quantity", min_value=1, value=1, step=1)

        colv1, colv2 = st.columns(2)
        with colv1:
            estimated_low = st.number_input("Estimated low value ($)", min_value=0.0, step=1.0)
        with colv2:
            estimated_high = st.number_input("Estimated high value ($)", min_value=0.0, step=1.0)

        confidence = st.selectbox("Confidence", ["Verified", "Inferred", "Unknown"], index=1)
        source = st.selectbox(
            "Source",
            ["Manual", "Default Library", "Tony History", "Approved Comp", "Web (Cited)"],
            index=0,
        )
        platform = st.text_input("Likely platform", value="Local marketplace")
        notes = st.text_area("Notes", value="", height=80)

        submitted = st.form_submit_button("Add simulated item")
        if submitted:
            if not name.strip():
                st.error("Name required.")
            else:
                item = {
                    "id": str(uuid.uuid4()),
                    "name": name.strip(),
                    "category": category.strip(),
                    "quantity": int(quantity),
                    "estimated_low": float(estimated_low),
                    "estimated_high": float(estimated_high),
                    "confidence": confidence,
                    "source": source,
                    "platform": platform.strip(),
                    "status": "Unassigned",
                    "notes": notes.strip(),
                    "phase": "prepurchase",
                }
                unit.setdefault("prepurchase_items", []).append(item)
                save_unit(unit)
                log_audit("add_prepurchase_item", {"unit_id": unit["unit_id"], "item_name": name})
                st.success("Item added.")

    # JSON import from ChatGPT
    st.markdown("#### Import items from ChatGPT")
    import_tabs = st.tabs(["Paste JSON", "Upload JSON file"])

    # Paste JSON tab
    with import_tabs[0]:
        with st.form("prepurchase_import_paste"):
            raw_json = st.text_area(
                "Paste JSON from ChatGPT here (list or {\"items\": [...]})",
                height=150,
                placeholder='[{"name": "Nintendo Switch", "estimated_low": 160, "estimated_high": 230}]',
            )
            import_btn = st.form_submit_button("Import simulated items from text")
            if import_btn:
                try:
                    new_items = import_items_from_json(raw_json, phase="prepurchase")
                    if not new_items:
                        st.warning("No valid items found in JSON.")
                    else:
                        unit.setdefault("prepurchase_items", []).extend(new_items)
                        save_unit(unit)
                        log_audit("import_prepurchase_items_text", {
                            "unit_id": unit["unit_id"],
                            "count": len(new_items),
                        })
                        st.success(f"Imported {len(new_items)} items from JSON text.")
                except Exception as e:
                    st.error(f"Import failed: {e}")

    # Upload JSON file tab
    with import_tabs[1]:
        uploaded = st.file_uploader(
            "Upload .json file from ChatGPT",
            type=["json"],
            key="prepurchase_file_uploader",
        )
        if uploaded is not None:
            if st.button("Import simulated items from file"):
                try:
                    raw_bytes = uploaded.read()
                    raw_json = raw_bytes.decode("utf-8-sig")
                    new_items = import_items_from_json(raw_json, phase="prepurchase")
                    if not new_items:
                        st.warning("No valid items found in file.")
                    else:
                        unit.setdefault("prepurchase_items", []).extend(new_items)
                        save_unit(unit)
                        log_audit("import_prepurchase_items_file", {
                            "unit_id": unit["unit_id"],
                            "count": len(new_items),
                        })
                        st.success(f"Imported {len(new_items)} items from JSON file.")
                except Exception as e:
                    st.error(f"File import failed: {e}")

    sim_items = unit.get("prepurchase_items", [])
    st.markdown("#### Simulated items")
    if sim_items:
        df = pd.DataFrame(sim_items)[
            ["name", "category", "quantity", "estimated_low", "estimated_high", "confidence", "source", "platform"]
        ]
        st.dataframe(df, use_container_width=True)
    else:
        st.caption("No simulated items yet.")

    overview = compute_unit_overview(unit)
    st.markdown("#### Math Summary")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Gross Low", f"${overview['low_gross']:.2f}")
    with col2:
        st.metric("Gross High", f"${overview['high_gross']:.2f}")
    with col3:
        st.metric("Expected Net", f"${overview['expected_net']:.2f}")

    if unit.get("status") == "prospective":
        if st.button("Mark unit as purchased"):
            unit["status"] = "purchased"
            unit["purchased_at"] = datetime.utcnow().isoformat() + "Z"
            save_unit(unit)
            for u in index["units"]:
                if u["unit_id"] == unit["unit_id"]:
                    u["status"] = "purchased"
            save_units_index(index)
            log_audit("mark_purchased", {"unit_id": unit["unit_id"]})
            st.success("Unit marked as purchased.")


# ---------- Work mode ----------

def ui_work_mode(unit):
    st.markdown("### Work Mode (After Purchase)")

    work_items = unit.get("work_items", [])
    item_names = ["(new item)"] + [f"{i['name']} (qty {i.get('quantity', 1)})" for i in work_items]
    choice = st.selectbox("Select item to edit or create", options=item_names, index=0)

    editing_existing = choice != "(new item)"
    existing_item = None
    idx = None
    if editing_existing:
        idx = item_names.index(choice) - 1
        existing_item = work_items[idx]

    with st.form("work_item_form"):
        name = st.text_input("Item name", value=(existing_item.get("name") if existing_item else ""))
        category = st.text_input("Category", value=(existing_item.get("category") if existing_item else "unknown"))
        quantity = st.number_input(
            "Quantity",
            min_value=1,
            value=int(existing_item.get("quantity", 1)) if existing_item else 1,
            step=1,
        )

        colv1, colv2 = st.columns(2)
        with colv1:
            estimated_low = st.number_input(
                "Low value ($)",
                min_value=0.0,
                step=1.0,
                value=float(existing_item.get("estimated_low", 0.0)) if existing_item else 0.0,
            )
        with colv2:
            estimated_high = st.number_input(
                "High value ($)",
                min_value=0.0,
                step=1.0,
                value=float(existing_item.get("estimated_high", 0.0)) if existing_item else 0.0,
            )

        confidence = st.selectbox(
            "Confidence",
            ["Verified", "Inferred", "Unknown"],
            index=["Verified", "Inferred", "Unknown"].index(
                existing_item.get("confidence", "Unknown")
            ) if existing_item else 2,
        )
        source = st.selectbox(
            "Source",
            ["Manual", "Default Library", "Tony History", "Approved Comp", "Web (Cited)"],
            index=0,
        )
        platform = st.text_input(
            "Platform",
            value=existing_item.get("platform", "Local marketplace") if existing_item else "Local marketplace",
        )
        status = st.selectbox(
            "Status",
            ["Sell", "Donate", "Dump", "Hold", "Unassigned"],
            index=["Sell", "Donate", "Dump", "Hold", "Unassigned"].index(
                existing_item.get("status", "Unassigned")
            ) if existing_item else 4,
        )
        notes = st.text_area(
            "Notes",
            value=existing_item.get("notes", "") if existing_item else "",
            height=80,
        )

        submitted = st.form_submit_button("Save item")
        if submitted:
            if not name.strip():
                st.error("Item name is required.")
            else:
                item_data = {
                    "id": existing_item.get("id", str(uuid.uuid4())) if existing_item else str(uuid.uuid4()),
                    "name": name.strip(),
                    "category": category.strip(),
                    "quantity": int(quantity),
                    "estimated_low": float(estimated_low),
                    "estimated_high": float(estimated_high),
                    "confidence": confidence,
                    "source": source,
                    "platform": platform.strip(),
                    "status": status,
                    "notes": notes.strip(),
                    "phase": "work",
                }
                if editing_existing:
                    work_items[idx] = item_data
                    log_event = "update_work_item"
                else:
                    work_items.append(item_data)
                    log_event = "add_work_item"
                unit["work_items"] = work_items
                save_unit(unit)
                log_audit(log_event, {"unit_id": unit["unit_id"], "item_name": name})
                st.success("Item saved.")

    st.markdown("#### Current work items")
    work_items = unit.get("work_items", [])
    if work_items:
        df = pd.DataFrame(work_items)[
            ["name", "status", "category", "quantity", "estimated_low", "estimated_high", "confidence", "source"]
        ]
        st.dataframe(df, use_container_width=True)
    else:
        st.caption("No work items yet.")

    st.markdown("---")
    st.markdown("#### Import items from ChatGPT")
    import_tabs = st.tabs(["Paste JSON", "Upload JSON file"])

    # Paste JSON tab
    with import_tabs[0]:
        with st.form("work_import_paste"):
            raw_json = st.text_area(
                "Paste JSON from ChatGPT here (list or {\"items\": [...]})",
                height=150,
                placeholder='[{"name": "Tool set", "estimated_low": 40, "estimated_high": 80}]',
            )
            import_btn = st.form_submit_button("Import work items from text")
            if import_btn:
                try:
                    new_items = import_items_from_json(raw_json, phase="work")
                    if not new_items:
                        st.warning("No valid items found in JSON.")
                    else:
                        unit.setdefault("work_items", []).extend(new_items)
                        save_unit(unit)
                        log_audit("import_work_items_text", {
                            "unit_id": unit["unit_id"],
                            "count": len(new_items),
                        })
                        st.success(f"Imported {len(new_items)} items from JSON text.")
                except Exception as e:
                    st.error(f"Import failed: {e}")

    # Upload JSON file tab
    with import_tabs[1]:
        uploaded = st.file_uploader(
            "Upload .json file from ChatGPT",
            type=["json"],
            key="work_file_uploader",
        )
        if uploaded is not None:
            if st.button("Import work items from file"):
                try:
                    raw_bytes = uploaded.read()
                    raw_json = raw_bytes.decode("utf-8-sig")
                    new_items = import_items_from_json(raw_json, phase="work")
                    if not new_items:
                        st.warning("No valid items found in file.")
                    else:
                        unit.setdefault("work_items", []).extend(new_items)
                        save_unit(unit)
                        log_audit("import_work_items_file", {
                            "unit_id": unit["unit_id"],
                            "count": len(new_items),
                        })
                        st.success(f"Imported {len(new_items)} items from JSON file.")
                except Exception as e:
                    st.error(f"File import failed: {e}")


# ---------- Tony mode ----------

def ui_tony_mode(unit):
    st.markdown("### Tony Mode (Summary View)")
    overview = compute_unit_overview(unit)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Gross Low", f"${overview['low_gross']:.2f}")
        st.metric("Gross High", f"${overview['high_gross']:.2f}")
    with col2:
        st.metric("Expected Gross", f"${overview['expected_gross']:.2f}")
        st.metric("Total Costs", f"${overview['total_costs']:.2f}")
    with col3:
        st.metric("Expected Net", f"${overview['expected_net']:.2f}")

    items = unit.get("work_items") or unit.get("prepurchase_items") or []
    if items:
        st.dataframe(pd.DataFrame(items), use_container_width=True)
    else:
        st.caption("No items yet.")


# ---------- Reports ----------

def ui_reports(unit):
    st.markdown("### Reports")
    d, i, l = unit_to_report_blocks(unit)

    st.markdown("#### Decision Summary")
    st.code(d, language="text")

    st.markdown("#### Inventory")
    st.code(i, language="text")

    st.markdown("#### Listings")
    st.code(l, language="text")

    json_bytes = json.dumps(unit, indent=2).encode("utf-8")
    st.download_button(
        "Download JSON",
        json_bytes,
        file_name=f"unit_{unit['unit_id']}.json",
        mime="application/json",
    )

    export_path = EXPORTS_DIR / f"unit_{unit['unit_id']}.json"
    with open(export_path, "wb") as f:
        f.write(json_bytes)


# ---------- Main ----------

def main():
    st.set_page_config(page_title="StorageUnit SimLay", layout="wide")
    ensure_dirs()

    if "current_unit_id" not in st.session_state:
        st.session_state["current_unit_id"] = None

    st.title("StorageUnit SimLay")

    select_or_create_unit()

    current_id = st.session_state.get("current_unit_id")
    if not current_id:
        st.info("Create or open a unit to begin.")
        return

    unit = load_unit(current_id)
    if unit is None:
        st.error("Could not load unit data.")
        return

    index = load_units_index()

    show_unit_header(unit)

    if unit.get("status") == "prospective":
        tabs = st.tabs(["Pre-Purchase Simulation", "Reports"])
        with tabs[0]:
            ui_prepurchase(unit, index)
        with tabs[1]:
            ui_reports(unit)
    else:
        tabs = st.tabs(["Pre-Purchase View", "Work Mode", "Tony Mode", "Reports"])
        with tabs[0]:
            ui_prepurchase(unit, index)
        with tabs[1]:
            ui_work_mode(unit)
        with tabs[2]:
            ui_tony_mode(unit)
        with tabs[3]:
            ui_reports(unit)


if __name__ == "__main__":
    main()
