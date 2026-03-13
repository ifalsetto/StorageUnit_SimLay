import json
import pandas as pd
import streamlit as st
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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


# ---------- Utilities ----------
def utc_now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def  -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UNITS_DIR.mkdir(parents=True, exist_ok=True)
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

    if not UNITS_INDEX_PATH.exists():
        UNITS_INDEX_PATH.write_text(json.dumps({"units": []}, indent=2), encoding="utf-8")


def log_audit(event: str, details: Dict[str, Any]) -> None:
    ensure_dirs()
    entry = {"timestamp": utc_now_iso(), "event": event, "details": details}
    with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
    f.write(json.dumps(entry) + "\n")


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        # utf-8-sig handles BOM files created by some Windows/PowerShell flows
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return default


def _write_json(path: Path, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def parse_number(value: Any, default: float = 0.0) -> float:
    """
    Robust float parser:
    - accepts numbers, None
    - accepts strings like "$1,200", "1,200.50", "(35)", "  40 ", "~50"
    """
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)

    s = str(value).strip()
    if not s:
        return default

    # common decorations
    s = s.replace("$", "").replace(",", "").replace("~", "").strip()

    # parentheses as negative
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative = True
        s = s[1:-1].strip()

    try:
        out = float(s)
        return -out if negative else out
    except Exception:
        return default


def parse_int(value: Any, default: int = 1) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    s = str(value).strip()
    if not s:
        return default
    # allow "2.0"
    try:
        return int(float(s))
    except Exception:
        return default


# ---------- Unit storage ----------
def  -> Dict[str, Any]:
    ensure_dirs()
    data = _read_json(UNITS_INDEX_PATH, {"units": []})
    if not isinstance(data, dict) or "units" not in data or not isinstance(data["units"], list):
        return {"units": []}
    return data


def save_units_index(index: Dict[str, Any]) -> None:
    _write_json(UNITS_INDEX_PATH, index)


def unit_path(unit_id: str) -> Path:
    return UNITS_DIR / f"{unit_id}.json"


def load_unit(unit_id: str) -> Optional[Dict[str, Any]]:
    path = unit_path(unit_id)
    data = _read_json(path, None)
    return data if isinstance(data, dict) else None


def save_unit(unit_data: Dict[str, Any]) -> None:
    _write_json(unit_path(unit_data["unit_id"]), unit_data)


# ---------- JSON import helper ----------
def import_items_from_json(raw: str, phase: str) -> List[Dict[str, Any]]:
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

    items: List[Dict[str, Any]] = []
    for obj in data:
        if not isinstance(obj, dict):
            continue

        name = (obj.get("name") or "").strip()
        if not name:
            continue

        item = {
            "id": str(uuid.uuid4()),
            "name": name,
            "category": (obj.get("category") or "unknown").strip(),
            "quantity": parse_int(obj.get("quantity"), default=1),
            "estimated_low": parse_number(obj.get("estimated_low"), default=0.0),
            "estimated_high": parse_number(obj.get("estimated_high"), default=0.0),
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
def compute_items_summary(items: List[Dict[str, Any]]) -> Tuple[float, float, float]:
    total_low = 0.0
    total_high = 0.0

    for item in items:
        q = parse_int(item.get("quantity"), default=1)
        v_low = parse_number(item.get("estimated_low"), default=0.0)
        v_high = parse_number(item.get("estimated_high"), default=0.0)
        total_low += v_low * q
        total_high += v_high * q

    total_expected = (total_low + total_high) / 2.0 if (total_low or total_high) else 0.0
    return total_low, total_high, total_expected


def compute_unit_overview(unit: Dict[str, Any]) -> Dict[str, float]:
    """
    Dump fees are NOT included anymore.
    Only:
      - current_bid
      - other_costs
    """
    pre_items = unit.get("prepurchase_items", []) or []
    work_items = unit.get("work_items", []) or []
    items = work_items if work_items else pre_items

    low, high, expected = compute_items_summary(items)

    current_bid = parse_number(unit.get("current_bid"), default=0.0)
    other_costs = parse_number(unit.get("other_costs"), default=0.0)

    total_costs = current_bid + other_costs
    expected_net = expected - total_costs

    return {
        "low_gross": low,
        "high_gross": high,
        "expected_gross": expected,
        "current_bid": current_bid,
        "other_costs": other_costs,
        "total_costs": total_costs,
        "expected_net": expected_net,
    }


def unit_to_report_blocks(unit: Dict[str, Any]) -> Tuple[str, str, str]:
    overview = compute_unit_overview(unit)
    items = unit.get("work_items") or unit.get("prepurchase_items") or []

    decision_lines: List[str] = []
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

    inv_lines: List[str] = ["=== Inventory ==="]
    for item in items:
        inv_lines.append(
            f"- {item.get('name', 'Unnamed item')} "
            f"(qty {parse_int(item.get('quantity'), 1)}, "
            f"value ${parse_number(item.get('estimated_low')):.2f}–${parse_number(item.get('estimated_high')):.2f}, "
            f"confidence: {item.get('confidence', 'Unknown')}, "
            f"source: {item.get('source', 'Manual')}, "
            f"status: {item.get('status', 'Unassigned')})"
        )
    inventory_block = "\n".join(inv_lines)

    listing_lines: List[str] = ["=== Listing Pack (Sell Items Only) ==="]
    for item in items:
        if item.get("status") == "Sell":
            name = item.get("name", "Unnamed item")
            qty = parse_int(item.get("quantity"), 1)
            platform = item.get("platform", "Local marketplace")
            v_low = parse_number(item.get("estimated_low"))
            v_high = parse_number(item.get("estimated_high"))
            listing_lines.append(f"{name} (x{qty})")
            listing_lines.append(f"Suggested platform: {platform}")
            listing_lines.append(f"Price band: ${v_low:.2f}–${v_high:.2f}")
            listing_lines.append("")
    listing_block = "\n".join(listing_lines)

    return decision_summary, inventory_block, listing_block


# ---------- UI helpers ----------
def select_or_create_unit() -> None:
    index = 
    units = index.get("units", [])

    st.sidebar.header("Units")
    existing_ids = [u.get("unit_id") for u in units if isinstance(u, dict) and u.get("unit_id")]
    existing_labels = [
        f"{u.get('unit_id')} – {u.get('status', 'unknown')}"
        for u in units
        if isinstance(u, dict) and u.get("unit_id")
    ]

    selected_label = None
    if existing_labels:
        selected_label = st.sidebar.selectbox(
            "Open existing unit:",
            options=["(none)"] + existing_labels,
            index=0,
        )

    if selected_label and selected_label != "(none)":
        idx = existing_labels.index(selected_label)
        st.session_state["current_unit_id"] = existing_ids[idx]

    st.sidebar.markdown("---")
    st.sidebar.subheader("Create new unit")

    if st.sidebar.button("Start new prospective unit"):
        unit_id = str(uuid.uuid4())[:8]
        unit = {
            "unit_id": unit_id,
            "status": "prospective",
            "created_at": utc_now_iso(),
            "purchased_at": None,
            "current_bid": 0.0,
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
        st.rerun()


def show_unit_header(unit: Dict[str, Any]) -> None:
    st.subheader(f"Unit ID: {unit['unit_id']}")
    st.write(f"Status: **{unit.get('status', 'unknown')}**")
    st.caption(f"Created at: {unit.get('created_at', 'N/A')} (UTC)")
    st.markdown("---")


# ---------- Pre-purchase UI ----------
def ui_prepurchase(unit: Dict[str, Any], index: Dict[str, Any]) -> None:
    st.markdown("### Pre-Purchase Simulation (Before Buying)")

    current_bid = st.number_input(
        "Current bid / expected price ($)",
        min_value=0.0,
        value=parse_number(unit.get("current_bid"), 0.0),
        step=10.0,
    )
    other_costs = st.number_input(
        "Other costs (optional, e.g. gas, tips)",
        min_value=0.0,
        value=parse_number(unit.get("other_costs"), 0.0),
        step=5.0,
    )

    unit["current_bid"] = float(current_bid)
    unit["other_costs"] = float(other_costs)
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
                st.rerun()

    st.markdown("#### Import items from ChatGPT")
    import_tabs = st.tabs(["Paste JSON", "Upload JSON file"])

    with import_tabs[0]:
        with st.form("prepurchase_import_paste"):
            raw_json = st.text_area(
                'Paste JSON from ChatGPT here (list or {"items": [...]})',
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
                        log_audit(
                            "import_prepurchase_items_text",
                            {"unit_id": unit["unit_id"], "count": len(new_items)},
                        )
                        st.success(f"Imported {len(new_items)} items.")
                        st.rerun()
                except Exception as e:
                    st.error(f"Import failed: {e}")

    with import_tabs[1]:
        uploaded = st.file_uploader(
            "Upload .json file from ChatGPT",
            type=["json"],
            key="prepurchase_file_uploader",
        )
        if uploaded is not None:
            if st.button("Import simulated items from file"):
                try:
                    raw_json = uploaded.read().decode("utf-8-sig")
                    new_items = import_items_from_json(raw_json, phase="prepurchase")
                    if not new_items:
                        st.warning("No valid items found in file.")
                    else:
                        unit.setdefault("prepurchase_items", []).extend(new_items)
                        save_unit(unit)
                        log_audit(
                            "import_prepurchase_items_file",
                            {"unit_id": unit["unit_id"], "count": len(new_items)},
                        )
                        st.success(f"Imported {len(new_items)} items.")
                        st.rerun()
                except Exception as e:
                    st.error(f"File import failed: {e}")

    sim_items = unit.get("prepurchase_items", []) or []
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
            unit["purchased_at"] = utc_now_iso()
            save_unit(unit)

            for u in index.get("units", []):
                if u.get("unit_id") == unit["unit_id"]:
                    u["status"] = "purchased"
            save_units_index(index)

            log_audit("mark_purchased", {"unit_id": unit["unit_id"]})
            st.success("Unit marked as purchased.")
            st.rerun()


# ---------- Work mode ----------
def ui_work_mode(unit: Dict[str, Any]) -> None:
    st.markdown("### Work Mode (After Purchase)")
    work_items = unit.get("work_items", []) or []

    item_names = ["(new item)"] + [f"{i.get('name','(unnamed)')} (qty {parse_int(i.get('quantity'), 1)})" for i in work_items]
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
            value=parse_int(existing_item.get("quantity"), 1) if existing_item else 1,
            step=1,
        )

        colv1, colv2 = st.columns(2)
        with colv1:
            estimated_low = st.number_input(
                "Low value ($)",
                min_value=0.0,
                step=1.0,
                value=parse_number(existing_item.get("estimated_low"), 0.0) if existing_item else 0.0,
            )
        with colv2:
            estimated_high = st.number_input(
                "High value ($)",
                min_value=0.0,
                step=1.0,
                value=parse_number(existing_item.get("estimated_high"), 0.0) if existing_item else 0.0,
            )

        confidence_list = ["Verified", "Inferred", "Unknown"]
        confidence = st.selectbox(
            "Confidence",
            confidence_list,
            index=confidence_list.index(existing_item.get("confidence", "Unknown")) if existing_item else 2,
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

        status_list = ["Sell", "Donate", "Dump", "Hold", "Unassigned"]
        status = st.selectbox(
            "Status",
            status_list,
            index=status_list.index(existing_item.get("status", "Unassigned")) if existing_item else 4,
        )

        notes = st.text_area("Notes", value=existing_item.get("notes", "") if existing_item else "", height=80)

        col_a, col_b = st.columns([1, 1])
        with col_a:
            submitted = st.form_submit_button("Save item")
        with col_b:
            delete_clicked = st.form_submit_button("Delete item") if editing_existing else False

        if delete_clicked and editing_existing and idx is not None:
            deleted = work_items.pop(idx)
            unit["work_items"] = work_items
            save_unit(unit)
            log_audit("delete_work_item", {"unit_id": unit["unit_id"], "item_id": deleted.get("id")})
            st.success("Item deleted.")
            st.rerun()

        if submitted:
            if not name.strip():
                st.error("Item name is required.")
            else:
                item_data = {
                    "id": (existing_item.get("id") if existing_item else str(uuid.uuid4())),
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

                if editing_existing and idx is not None:
                    work_items[idx] = item_data
                    log_event = "update_work_item"
                else:
                    work_items.append(item_data)
                    log_event = "add_work_item"

                unit["work_items"] = work_items
                save_unit(unit)
                log_audit(log_event, {"unit_id": unit["unit_id"], "item_name": name})
                st.success("Item saved.")
                st.rerun()

    st.markdown("#### Current work items")
    work_items = unit.get("work_items", []) or []
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

    with import_tabs[0]:
        with st.form("work_import_paste"):
            raw_json = st.text_area(
                'Paste JSON from ChatGPT here (list or {"items": [...]})',
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
                        log_audit("import_work_items_text", {"unit_id": unit["unit_id"], "count": len(new_items)})
                        st.success(f"Imported {len(new_items)} items.")
                        st.rerun()
                except Exception as e:
                    st.error(f"Import failed: {e}")

    with import_tabs[1]:
        uploaded = st.file_uploader(
            "Upload .json file from ChatGPT",
            type=["json"],
            key="work_file_uploader",
        )
        if uploaded is not None:
            if st.button("Import work items from file"):
                try:
                    raw_json = uploaded.read().decode("utf-8-sig")
                    new_items = import_items_from_json(raw_json, phase="work")
                    if not new_items:
                        st.warning("No valid items found in file.")
                    else:
                        unit.setdefault("work_items", []).extend(new_items)
                        save_unit(unit)
                        log_audit("import_work_items_file", {"unit_id": unit["unit_id"], "count": len(new_items)})
                        st.success(f"Imported {len(new_items)} items.")
                        st.rerun()
                except Exception as e:
                    st.error(f"File import failed: {e}")


# ---------- Tony mode ----------
def ui_tony_mode(unit: Dict[str, Any]) -> None:
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
def ui_reports(unit: Dict[str, Any]) -> None:
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

    if st.button("Save export file to /exports"):
        ensure_dirs()
        export_path = EXPORTS_DIR / f"unit_{unit['unit_id']}.json"
        export_path.write_bytes(json_bytes)
        st.success(f"Saved: {export_path}")


# ---------- Main ----------
def main() -> None:
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

    index = 
    show_unit_header(unit)

    if unit.get("status") == "prospective":
        tabs = st.tabs(["Pre-Purchase Simulation", "Reports"])
        with tabs[0]:
            ui_prepurchase(unit, index)
        with tabs[1]:
            ui_reports(unit)
    else:
        tabs = st.tabs(["Pre-Purchase", "Work Mode", "Tony Mode", "Reports"])

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
