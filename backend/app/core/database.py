import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable

BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = BASE_DIR / "data" / "simlay.db"

SCHEMA = r"""
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    run_short TEXT UNIQUE NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    profile_name TEXT NOT NULL,
    profile_snapshot TEXT NOT NULL CHECK(json_valid(profile_snapshot)),
    media_type TEXT DEFAULT 'photos',
    media_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'created',
    total_items INTEGER DEFAULT 0,
    total_verified INTEGER DEFAULT 0,
    total_inferred INTEGER DEFAULT 0,
    total_unknown INTEGER DEFAULT 0,
    csv_exported_at TEXT,
    audit_exported_at TEXT,
    errors TEXT CHECK(errors IS NULL OR json_valid(errors)),
    warnings TEXT CHECK(warnings IS NULL OR json_valid(warnings))
);

CREATE TABLE IF NOT EXISTS media_inputs (
    media_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_type TEXT NOT NULL,
    sequence_order INTEGER,
    timestamp_in_video REAL,
    processed_at TEXT,
    vision_response TEXT CHECK(vision_response IS NULL OR json_valid(vision_response)),
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS items (
    item_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    raw_name TEXT,
    final_name TEXT NOT NULL,
    normalized_name TEXT,
    brand TEXT,
    category TEXT,
    subcategory TEXT,
    quantity INTEGER DEFAULT 1,
    visible_condition TEXT DEFAULT 'Unknown',
    confidence TEXT NOT NULL,
    confidence_reason TEXT,
    source TEXT NOT NULL DEFAULT 'User Visual',
    notes TEXT,
    representative_image_id TEXT,
    detected_in_media TEXT CHECK(detected_in_media IS NULL OR json_valid(detected_in_media)),
    flag_unknown INTEGER DEFAULT 0,
    flag_duplicate_suspect INTEGER DEFAULT 0,
    flag_missing_comps INTEGER DEFAULT 0,
    flag_high_variance INTEGER DEFAULT 0,
    flag_possible_collectible INTEGER DEFAULT 0,
    sort_tier INTEGER DEFAULT 99,
    sort_order INTEGER DEFAULT 999,
    value_p25 REAL,
    value_p50 REAL,
    value_p75 REAL,
    value_export REAL,
    value_source TEXT,
    valuation_passed_gates INTEGER DEFAULT 0,
    wix_handle TEXT UNIQUE,
    wix_sku TEXT UNIQUE,
    wix_exported INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE,
    FOREIGN KEY (representative_image_id) REFERENCES media_inputs(media_id)
);

CREATE TABLE IF NOT EXISTS evidence (
    evidence_id TEXT PRIMARY KEY,
    item_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_name TEXT,
    url TEXT,
    url_title TEXT,
    url_platform TEXT,
    screenshot_path TEXT,
    price REAL,
    currency TEXT DEFAULT 'USD',
    condition TEXT,
    sale_date TEXT,
    listing_type TEXT NOT NULL DEFAULT 'sold',
    is_active_listing INTEGER DEFAULT 0,
    discounted_price REAL,
    is_bundle INTEGER DEFAULT 0,
    is_outlier INTEGER DEFAULT 0,
    notes TEXT,
    last_refreshed_at TEXT,
    refresh_status TEXT DEFAULT 'never',
    included_in_valuation INTEGER DEFAULT 1,
    exclusion_reason TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (item_id) REFERENCES items(item_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ocr_candidates (
    candidate_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    media_id TEXT,
    source_image TEXT NOT NULL,
    provider TEXT NOT NULL,
    candidate_hash TEXT NOT NULL,
    candidate_name TEXT NOT NULL,
    brand_guess TEXT,
    model_guess TEXT,
    serial_guess TEXT,
    barcode_guess TEXT,
    price_guess TEXT,
    evidence_text TEXT CHECK(evidence_text IS NULL OR json_valid(evidence_text)),
    raw_ocr TEXT CHECK(raw_ocr IS NULL OR json_valid(raw_ocr)),
    avg_confidence REAL DEFAULT 0,
    simlay_usefulness_score INTEGER DEFAULT 0,
    ocr_status TEXT NOT NULL DEFAULT 'needs_review',
    review_status TEXT NOT NULL DEFAULT 'pending_review',
    notes TEXT,
    promoted_item_id TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(run_id, candidate_hash),
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE,
    FOREIGN KEY (media_id) REFERENCES media_inputs(media_id),
    FOREIGN KEY (promoted_item_id) REFERENCES items(item_id)
);

CREATE TABLE IF NOT EXISTS exports (
    export_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    export_type TEXT NOT NULL,
    file_path TEXT NOT NULL,
    row_count INTEGER,
    validation_passed INTEGER DEFAULT 0,
    validation_errors TEXT CHECK(validation_errors IS NULL OR json_valid(validation_errors)),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS audit_events (
    audit_id TEXT PRIMARY KEY,
    run_id TEXT,
    entity_type TEXT,
    entity_id TEXT,
    action TEXT NOT NULL,
    payload TEXT CHECK(payload IS NULL OR json_valid(payload)),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_items_run_id ON items(run_id);
CREATE INDEX IF NOT EXISTS idx_media_run_id ON media_inputs(run_id);
CREATE INDEX IF NOT EXISTS idx_evidence_item_id ON evidence(item_id);
CREATE INDEX IF NOT EXISTS idx_ocr_candidates_run_id ON ocr_candidates(run_id);
CREATE INDEX IF NOT EXISTS idx_ocr_candidates_media_id ON ocr_candidates(media_id);
CREATE INDEX IF NOT EXISTS idx_ocr_candidates_review_status ON ocr_candidates(review_status);
CREATE INDEX IF NOT EXISTS idx_exports_run_id ON exports(run_id);
CREATE INDEX IF NOT EXISTS idx_runs_history_list ON runs(
    created_at DESC,
    run_id,
    run_short,
    profile_name,
    media_type,
    status,
    total_items
);
"""

def connect(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

@contextmanager
def db_session(db_path: str | Path = DEFAULT_DB_PATH):
    conn = connect(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db(db_path: str | Path = DEFAULT_DB_PATH) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)
        conn.commit()

def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row else None

def rows_to_dicts(rows: Iterable[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(r) for r in rows]

def to_json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)

def from_json_text(value: str | None, default: Any = None) -> Any:
    if value is None:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default
