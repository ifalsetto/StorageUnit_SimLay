import streamlit as st
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
import datetime
import uuid


# ---------- Data Models ----------

@dataclass
class IDProtocolLog:
    started_at: datetime.datetime
    finished_at: Optional[datetime.datetime] = None
    inspector: Optional[str] = None
    marks_found: str = ""
    photos: List[str] = None  # just labels / placeholders in this demo
    research_summary: str = ""
    search_queries: str = ""
    value_band_choice: str = ""
    category_choice: str = ""
    result: str = ""  # hold / sell_as_is / escalate
    justification_if_sell: str = ""


@dataclass
class Item:
    id: str
    name: str
    category: str           # furniture / art / tools / etc.
    material: str           # wood / metal / bronze / etc.
    weight_class: str       # light / medium / heavy
    high_signal_flag: bool  # manual "this might be valuable"
    id_protocol_status: str # "not_required" | "pending" | "completed"
    id_protocol_result: str # "" | "hold" | "sell_as_is" | "escalate"


# ---------- Helper Logic ----------

def should_run_id_protocol(item: Item) -> bool:
    """Decide if this item should trigger the Unknown ID Protocol."""
    if item.category in ["art", "sculpture", "collectible"]:
        return True
    if item.material in ["bronze", "stone", "marble"]:
        return True
    if item.weight_class == "heavy":
        return True
    if item.high_signal_flag:
        return True
    return False


def get_item_by_id(item_id: str) -> Optional[Item]:
    for it in st.session_state.inventory:
        if it.id == item_id:
            return it
    return None


def update_item(updated: Item):
    for idx, it in enumerate(st.session_state.inventory):
        if it.id == updated.id:
            st.session_state.inventory[idx] = updated
            break


def ensure_session_state():
    if "inventory" not in st.session_state:
        # Demo inventory: one bronze sculpture + two normal items
        st.session_state.inventory: List[Item] = [
            Item(
                id=str(uuid.uuid4()),
                name="Bronze Western Sculpture",
                category="sculpture",
                material="bronze",
                weight_class="heavy",
                high_signal_flag=True,
                id_protocol_status="pending",
                id_protocol_result=""
            ),
            Item(
                id=str(uuid.uuid4()),
                name="IKEA Bookshelf",
                category="furniture",
                material="wood",
                weight_class="medium",
                high_signal_flag=False,
                id_protocol_status="not_required",
                id_protocol_result=""
            ),
            Item(
                id=str(uuid.uuid4()),
                name="Plastic Storage Bins (x4)",
                category="storage",
                material="plastic",
                weight_class="light",
                high_signal_flag=False,
                id_protocol_status="not_required",
                id_protocol_result=""
            ),
        ]

    if "selected_item_id" not in st.session_state:
        st.session_state.selected_item_id = None

    if "id_protocol_state" not in st.session_state:
        # per-item state: step, log, checklists, etc.
        st.session_state.id_protocol_state: Dict[str, Dict] = {}

    if "audit_log" not in st.session_state:
        st.session_state.audit_log: List[Dict] = []


# ---------- ID Protocol UI ----------

def start_id_protocol(item: Item):
    state = st.session_state.id_protocol_state
    if item.id not in state:
        state[item.id] = {
            "step": 1,
            "checklist": {
                "flipped": False,
                "base_checked": False,
                "signature_checked": False,
                "numbers_checked": False,
                "plaques_checked": False,
                "foundry_checked": False,
            },
            "marks_found": "",
            "photos": [],
            "search_queries": "",
            "research_summary": "",
            "category_choice": "",
            "value_band_choice": "",
            "decision": "",
            "justification": "",
            "log": IDProtocolLog(
                started_at=datetime.datetime.utcnow(),
                photos=[]
            )
        }


def render_id_protocol(item: Item):
    """
    Multi-step 10-minute ID protocol.
    Uses st.session_state.id_protocol_state[item.id]["step"] to track progress.
    """
    state = st.session_state.id_protocol_state[item.id]
    step = state["step"]

    st.subheader("Unknown ID Protocol (Required Before Disposal / Cheap Sale)")
    st.caption("This protects you from giving away high-value items by accident.")

    # Step 1: Physical inspection checklist
    if step == 1:
        st.markdown("### Step 1 — Physical Inspection")

        cl = state["checklist"]
        cl["flipped"] = st.checkbox("Flipped item / checked underside", value=cl["flipped"])
        cl["base_checked"] = st.checkbox("Checked base / edges / seams", value=cl["base_checked"])
        cl["signature_checked"] = st.checkbox("Looked for signature / maker's mark", value=cl["signature_checked"])
        cl["numbers_checked"] = st.checkbox("Looked for numbers (e.g. 6/100, serials)", value=cl["numbers_checked"])
        cl["plaques_checked"] = st.checkbox("Looked for plaques / labels", value=cl["plaques_checked"])
        cl["foundry_checked"] = st.checkbox("Looked for foundry / country stamps", value=cl["foundry_checked"])

        marks = st.text_area(
            "Marks / text you can see (names, numbers, words):",
            value=state["marks_found"]
        )
        state["marks_found"] = marks

        all_done = all(cl.values())
        if not all_done:
            st.warning("Complete all checkboxes before continuing.")
        if st.button("Continue to Photos", disabled=not all_done):
            state["step"] = 2

    # Step 2: Photos (just labels/placeholders in this demo)
    elif step == 2:
        st.markdown("### Step 2 — Photos (Evidence)")

        st.write("In the real app, you would capture/upload photos here.")
        st.write("For now, add labels to represent the photos you took:")

        new_label = st.text_input("Photo label (e.g. 'Full item front', 'Signature close-up'):")
        if st.button("Add Photo Label") and new_label.strip():
            state["photos"].append(new_label.strip())

        if not state["photos"]:
            st.info("Add at least 3 photo labels to continue.")
        else:
            st.write("Current photo labels:")
            for p in state["photos"]:
                st.markdown(f"- {p}")

        if st.button("Continue to Quick Research", disabled=len(state["photos"]) < 3):
            state["step"] = 3

    # Step 3: Quick research
    elif step == 3:
        st.markdown("### Step 3 — Quick Research")

        st.write("Type the exact text you see on the item (names, numbers, titles).")
        queries = st.text_area("Search terms / what you Googled:", value=state["search_queries"])
        state["search_queries"] = queries

        st.write("Summarize what you found (or didn't find) in 1–3 sentences.")
        summary = st.text_area("Research summary:", value=state["research_summary"])
        state["research_summary"] = summary

        if st.button("Continue to Category"):
            state["step"] = 4

    # Step 4: Category classification
    elif step == 4:
        st.markdown("### Step 4 — Category Classification")

        category_options = [
            "Fine Art / Sculpture",
            "Decorative Art",
            "Collectible / Estate",
            "Tool / Equipment",
            "Furniture",
            "Unknown (High Risk)"
        ]
        category_choice = st.radio(
            "Pick the best category for this item:",
            category_options,
            index=category_options.index(state["category_choice"])
            if state["category_choice"] in category_options else 0
        )
        state["category_choice"] = category_choice

        if st.button("Continue to Value Band"):
            state["step"] = 5

    # Step 5: Value band estimate
    elif step == 5:
        st.markdown("### Step 5 — Value Band Estimate")

        band_options = [
            "< $200",
            "$200–$1,000",
            "$1,000–$5,000",
            "$5,000+"
        ]
        selected = st.radio(
            "Which price band best fits this item based on your research?",
            band_options,
            index=band_options.index(state["value_band_choice"])
            if state["value_band_choice"] in band_options else 0
        )
        state["value_band_choice"] = selected

        if st.button("Continue to Final Decision"):
            state["step"] = 6

    # Step 6: Final action gate
    elif step == 6:
        st.markdown("### Step 6 — Final Decision")

        decision_options = [
            "HOLD — Pending further review (recommended)",
            "SELL AS-IS — I accept the risk",
            "ESCALATE — I want expert review"
        ]
        decision = st.radio(
            "What do you want to do with this item now?",
            decision_options,
            index=decision_options.index(state["decision"])
            if state["decision"] in decision_options else 0
        )
        state["decision"] = decision

        justification = state["justification"]
        require_justification = (
            decision == "SELL AS-IS — I accept the risk"
            and state["value_band_choice"] != "< $200"
        )

        if require_justification:
            st.warning(
                "You chose SELL AS-IS on an item you believe could be worth more than $200."
            )
            justification = st.text_area(
                "Explain why you're okay possibly leaving money on the table:",
                value=justification
            )
            state["justification"] = justification

        can_finish = not require_justification or (
            justification and len(justification.strip()) >= 20
        )

        if require_justification and not can_finish:
            st.info(
                "Write at least a short explanation (20+ characters) before confirming."
            )

        if st.button("Confirm & Save", disabled=not can_finish):
            # Finalize log
            log: IDProtocolLog = state["log"]
            log.finished_at = datetime.datetime.utcnow()
            log.inspector = "Tony/Worker"  # later tie to user auth
            log.marks_found = state["marks_found"]
            log.photos = state["photos"]
            log.search_queries = state["search_queries"]
            log.research_summary = state["research_summary"]
            log.category_choice = state["category_choice"]
            log.value_band_choice = state["value_band_choice"]

            if decision.startswith("HOLD"):
                log.result = "hold"
                item.id_protocol_result = "hold"
            elif decision.startswith("SELL AS-IS"):
                log.result = "sell_as_is"
                item.id_protocol_result = "sell_as_is"
            else:
                log.result = "escalate"
                item.id_protocol_result = "escalate"

            item.id_protocol_status = "completed"
            update_item(item)

            # Write to audit log
            st.session_state.audit_log.append({
                "timestamp": datetime.datetime.utcnow().isoformat(),
                "item_id": item.id,
                "item_name": item.name,
                "log": asdict(log),
            })

            st.success("ID Protocol completed and logged.")
            # Keep at step 6 but effectively locked
            state["step"] = 6
            st.stop()


# ---------- Item Detail / Tony Mode-ish View ----------

def render_item_detail(item: Item):
    st.header(item.name)
    st.write(f"Category: `{item.category}`")
    st.write(f"Material: `{item.material}`")
    st.write(f"Weight: `{item.weight_class}`")
    st.write(f"High-signal flag: `{item.high_signal_flag}`")
    st.write(f"ID Protocol Status: `{item.id_protocol_status}`")
    if item.id_protocol_result:
        st.write(f"ID Protocol Result: `{item.id_protocol_result}`")

    # If protocol is required and not completed, force the flow
    if item.id_protocol_status == "pending":
        st.warning(
            "This item requires the Unknown ID Protocol before it can be sold, "
            "donated, or scrapped."
        )
        start_id_protocol(item)
        render_id_protocol(item)
        return

    # If protocol should run but hasn't yet
    if should_run_id_protocol(item) and item.id_protocol_status != "completed":
        st.info(
            "This looks like a high-signal item. Run the Unknown ID Protocol "
            "to protect upside."
        )
        if st.button("Run Unknown ID Protocol Now"):
            item.id_protocol_status = "pending"
            update_item(item)
            start_id_protocol(item)
            render_id_protocol(item)
            return

    # If protocol already completed, show high-level result + normal controls
    if item.id_protocol_status == "completed":
        if item.id_protocol_result == "hold":
            st.info(
                "Protocol result: HOLD — Pending further review. "
                "Destructive actions should be avoided."
            )
        elif item.id_protocol_result == "sell_as_is":
            st.warning(
                "Protocol result: SELL AS-IS. Proceed carefully; some upside may remain."
            )
        elif item.id_protocol_result == "escalate":
            st.error(
                "Protocol result: ESCALATE — Needs expert review before selling."
            )

    st.markdown("---")
    st.subheader("Item Actions (Demo)")

    # In a real app, you'd disable these buttons based on protocol result.
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.button("Sell", key=f"sell_{item.id}")
    with col2:
        st.button("Dump", key=f"dump_{item.id}")
    with col3:
        st.button("Donate", key=f"donate_{item.id}")
    with col4:
        st.button("Hold", key=f"hold_{item.id}")


# ---------- Main App ----------

def main():
    st.set_page_config(
        page_title="StorageUnit SimLay — Unknown ID Protocol Demo",
        layout="wide"
    )
    ensure_session_state()

    st.title("StorageUnit SimLay — Unknown ID Protocol Demo")

    left, right = st.columns([1, 2], gap="large")

    with left:
        st.subheader("Inventory")
        options = {it.name: it.id for it in st.session_state.inventory}
        selected_name = st.selectbox("Select an item:", ["(None)"] + list(options.keys()))

        if selected_name != "(None)":
            st.session_state.selected_item_id = options[selected_name]
        else:
            st.session_state.selected_item_id = None

        st.markdown("### Audit Log (last 5)")
        if st.session_state.audit_log:
            for entry in st.session_state.audit_log[-5:][::-1]:
                st.markdown(
                    f"- `{entry['timestamp']}` — **{entry['item_name']}** "
                    f"→ result: `{entry['log']['result']}`"
                )
        else:
            st.caption("No ID protocol logs yet.")

    with right:
        if st.session_state.selected_item_id:
            item = get_item_by_id(st.session_state.selected_item_id)
            if item:
                render_item_detail(item)
        else:
            st.info("Select an item from the left to view details or run the ID protocol.")


if __name__ == "__main__":
    main()
