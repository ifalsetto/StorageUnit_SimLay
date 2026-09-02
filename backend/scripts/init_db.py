from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.database import DEFAULT_DB_PATH, db_session, init_db
from app.core.market_schema import ensure_market_schema

if __name__ == "__main__":
    init_db(DEFAULT_DB_PATH)
    with db_session(DEFAULT_DB_PATH) as conn:
        ensure_market_schema(conn)
    print(f"Initialized database with market intelligence schema: {DEFAULT_DB_PATH}")
