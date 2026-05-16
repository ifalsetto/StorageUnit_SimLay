import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.database import init_db, db_session
from app.routers.runs import create_run
from app.schemas import CreateRunRequest, ItemCreate, EvidenceCreate
from app.routers.items import create_item
from app.routers.evidence import add_evidence

if __name__ == "__main__":
    init_db()
    run = create_run(CreateRunRequest(profile_name="default", media_type="photos"))
    item = create_item(ItemCreate(
        run_id=run["run_id"],
        final_name="RAGU Projector",
        category="Electronics",
        quantity=1,
        visible_condition="Used",
        confidence="Inferred",
        confidence_reason="Item type known, exact model not visually verified in sample seed.",
        source="User Visual",
        notes="Similar model, tested working, no remote"
    ))
    for price in [32, 35, 30]:
        add_evidence(EvidenceCreate(item_id=item["item_id"], source_type="url", source_name="user_url", url="https://example.com/ebay-sold-comp", url_platform="ebay", price=price, listing_type="sold", notes="Seed sold comparable"))
    print("Seeded run:", run)
    print("Seeded item:", item)
