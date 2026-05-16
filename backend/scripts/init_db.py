from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.database import init_db, DEFAULT_DB_PATH

if __name__ == "__main__":
    init_db(DEFAULT_DB_PATH)
    print(f"Initialized database: {DEFAULT_DB_PATH}")
