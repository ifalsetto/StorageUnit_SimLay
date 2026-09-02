from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import re
import socket
import sqlite3
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import keyring

REQUIRED_SOURCE_NAMES = {
    "package.json", "package-lock.json", "pyproject.toml", "requirements.txt",
    "dockerfile", "docker-compose.yml", ".gitignore", ".env", ".env.example",
    "readme.md", "license", "vite.config.js", "tsconfig.json",
}
OPAQUE_PATTERNS = [
    re.compile(r"^[0-9a-f]{20,}$", re.I),
    re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", re.I),
    re.compile(r"^(file|image|img|photo|video|document|doc|download|upload)[_-]?[0-9a-f]{12,}$", re.I),
    re.compile(r"^[a-z]{1,8}_[0-9a-f]{16,}$", re.I),
]
KIND_BY_EXT = {
    ".jpg": "Image", ".jpeg": "Image", ".png": "Image", ".webp": "Image", ".gif": "Image",
    ".mp4": "Video", ".mov": "Video", ".mkv": "Video",
    ".pdf": "Document", ".doc": "Document", ".docx": "Document", ".txt": "Document", ".md": "Document",
    ".zip": "Archive", ".7z": "Archive", ".rar": "Archive",
    ".db": "Database", ".sqlite": "Database", ".sqlite3": "Database",
    ".csv": "Export", ".xlsx": "Export", ".json": "Data", ".yaml": "Data", ".yml": "Data",
    ".ps1": "Script", ".py": "Script", ".js": "Script", ".ts": "Script", ".cmd": "Script", ".bat": "Script",
    ".exe": "Installer", ".msi": "Installer",
}
PROJECT_HINTS = [
    (("simlay", "storageunit", "storage-unit", "falsetech resale", "falsetech-resale"), "SimLay", "simlay"),
    (("continuity",), "Continuity", None),
    (("apex",), "Apex-Dashboard", None),
    (("locktext",), "LockText", None),
    (("roadwatch",), "RoadWatch", None),
    (("beacon", "knowledgebase"), "FalseTech-OS", None),
    (("music", "aimusic"), "AI-Music-Lab", None),
]
IGNORED_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".next", "dist", "build"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def project_for(path: Path) -> tuple[str, str | None]:
    text = str(path).lower()
    for terms, label, key in PROJECT_HINTS:
        if any(term in text for term in terms):
            return label, key
    return "FalseTech", None


def kind_for(path: Path) -> str:
    return KIND_BY_EXT.get(path.suffix.lower(), "File")


def is_opaque_name(path: Path) -> bool:
    if path.name.lower() in REQUIRED_SOURCE_NAMES:
        return False
    stem = path.stem
    if any(pattern.match(stem) for pattern in OPAQUE_PATTERNS):
        return True
    compact = re.sub(r"[^A-Za-z0-9]", "", stem)
    if not compact:
        return True
    digit_ratio = sum(ch.isdigit() for ch in compact) / len(compact)
    return len(compact) >= 20 and digit_ratio > 0.45


def under_any(path: Path, roots: list[Path]) -> bool:
    resolved = path.resolve()
    for root in roots:
        try:
            resolved.relative_to(root.resolve())
            return True
        except Exception:
            continue
    return False


def canonical_name(path: Path) -> str:
    project, _ = project_for(path)
    stamp = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).strftime("%Y-%m-%d-%H%M%S")
    return f"{project}-{kind_for(path)}-{stamp}{path.suffix.lower()}"


def safe_rename(path: Path, rename_roots: list[Path]) -> tuple[Path, str | None]:
    if not is_opaque_name(path):
        return path, None
    if ".git" in path.parts or not under_any(path, rename_roots):
        return path, "opaque_name_cataloged_not_renamed"
    target = path.with_name(canonical_name(path))
    counter = 2
    while target.exists() and target != path:
        target = path.with_name(f"{target.stem}-{counter}{target.suffix}")
        counter += 1
    original = path.name
    path.rename(target)
    return target, f"opaque_user_facing_name:{original}"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iter_files(roots: list[Path]):
    for root in roots:
        if not root.exists():
            continue
        for base, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d.lower() not in IGNORED_DIRS]
            for name in files:
                yield Path(base) / name


class Settings:
    def __init__(self, path: Path):
        data = json.loads(path.read_text(encoding="utf-8"))
        self.config_path = path
        self.root = Path(data.get("root", r"C:\FalseTech"))
        self.db_path = Path(data.get("db_path", self.root / "Continuity" / "FalseTech-Node-Cache.db"))
        self.supabase_url = data["supabase_url"].rstrip("/")
        self.publishable_key = data["publishable_key"]
        self.email = data.get("email", "")
        self.device_name = data["device_name"]
        self.device_type = data.get("device_type", "desktop")
        self.scan_roots = [Path(p) for p in data.get("scan_roots", [])]
        self.rename_roots = [Path(p) for p in data.get("rename_roots", [])]
        self.poll_seconds = max(15, int(data.get("poll_seconds", 60)))


class LocalState:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS queue(
            operation_id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL,
            project_key TEXT,
            entity_type TEXT,
            entity_id TEXT,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL,
            sent_at TEXT
        );
        CREATE TABLE IF NOT EXISTS files(
            path TEXT PRIMARY KEY,
            content_hash TEXT,
            size_bytes INTEGER,
            mtime_ns INTEGER,
            canonical_name TEXT,
            original_name TEXT,
            project_key TEXT,
            last_seen_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_queue_unsent ON queue(sent_at);
        CREATE INDEX IF NOT EXISTS idx_files_hash ON files(content_hash);
        """)
        self.conn.commit()

    def get(self, key: str, default: str | None = None) -> str | None:
        row = self.conn.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def set(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO state(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        self.conn.commit()

    def enqueue(self, event_type: str, project_key: str | None, payload: dict[str, Any], entity_type: str | None = None, entity_id: str | None = None) -> str:
        operation_id = str(uuid.uuid4())
        self.conn.execute(
            "INSERT INTO queue(operation_id,event_type,project_key,entity_type,entity_id,payload,created_at) VALUES(?,?,?,?,?,?,?)",
            (operation_id, event_type, project_key, entity_type, entity_id, json.dumps(payload, sort_keys=True), utc_now()),
        )
        self.conn.commit()
        return operation_id

    def unsent(self, limit: int = 250) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT * FROM queue WHERE sent_at IS NULL ORDER BY created_at LIMIT ?", (limit,)).fetchall()
        return [{
            "operation_id": row["operation_id"], "event_type": row["event_type"], "project_key": row["project_key"],
            "entity_type": row["entity_type"], "entity_id": row["entity_id"], "payload": json.loads(row["payload"]),
            "created_at": row["created_at"],
        } for row in rows]

    def mark_sent(self, operation_ids: list[str]) -> None:
        if not operation_ids:
            return
        now = utc_now()
        self.conn.executemany("UPDATE queue SET sent_at=? WHERE operation_id=?", [(now, op) for op in operation_ids])
        self.conn.commit()

    def file_changed(self, path: Path, size: int, mtime_ns: int) -> bool:
        row = self.conn.execute("SELECT size_bytes,mtime_ns FROM files WHERE path=?", (str(path),)).fetchone()
        return not row or row["size_bytes"] != size or row["mtime_ns"] != mtime_ns

    def upsert_file(self, path: Path, digest: str, size: int, mtime_ns: int, canonical: str, original: str, project_key: str | None) -> None:
        self.conn.execute("""
            INSERT INTO files(path,content_hash,size_bytes,mtime_ns,canonical_name,original_name,project_key,last_seen_at)
            VALUES(?,?,?,?,?,?,?,?)
            ON CONFLICT(path) DO UPDATE SET content_hash=excluded.content_hash,size_bytes=excluded.size_bytes,
            mtime_ns=excluded.mtime_ns,canonical_name=excluded.canonical_name,original_name=excluded.original_name,
            project_key=excluded.project_key,last_seen_at=excluded.last_seen_at
        """, (str(path), digest, size, mtime_ns, canonical, original, project_key, utc_now()))
        self.conn.commit()


class FalseTechClient:
    def __init__(self, settings: Settings, state: LocalState):
        self.s = settings
        self.state = state
        self.access_token: str | None = None

    def login(self, password: str | None = None) -> None:
        if not self.s.email:
            raise RuntimeError("email missing from FalseTech-Node.json")
        refresh = keyring.get_password("FalseTech-Node", self.s.email)
        if refresh:
            response = httpx.post(
                f"{self.s.supabase_url}/auth/v1/token?grant_type=refresh_token",
                headers={"apikey": self.s.publishable_key, "Content-Type": "application/json"},
                json={"refresh_token": refresh}, timeout=30,
            )
            if response.status_code < 400:
                return self._accept_session(response.json())
        if password is None:
            import getpass
            password = getpass.getpass(f"Supabase password for {self.s.email}: ")
        response = httpx.post(
            f"{self.s.supabase_url}/auth/v1/token?grant_type=password",
            headers={"apikey": self.s.publishable_key, "Content-Type": "application/json"},
            json={"email": self.s.email, "password": password}, timeout=30,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"login failed ({response.status_code}): {response.text[:300]}")
        self._accept_session(response.json())

    def _accept_session(self, data: dict[str, Any]) -> None:
        self.access_token = data["access_token"]
        keyring.set_password("FalseTech-Node", self.s.email, data["refresh_token"])

    def rpc(self, name: str, payload: dict[str, Any]) -> Any:
        if not self.access_token:
            self.login()
        headers = {
            "apikey": self.s.publishable_key,
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        response = httpx.post(f"{self.s.supabase_url}/rest/v1/rpc/{name}", headers=headers, json=payload, timeout=45)
        if response.status_code == 401:
            self.access_token = None
            self.login()
            return self.rpc(name, payload)
        if response.status_code >= 400:
            raise RuntimeError(f"{name} failed ({response.status_code}): {response.text[:500]}")
        return response.json() if response.text else None

    def ensure_device(self) -> str:
        result = self.rpc("falsetech_device_upsert", {
            "p_display_name": self.s.device_name,
            "p_hostname": socket.gethostname(),
            "p_platform": f"{sys.platform}:{os.name}",
            "p_device_type": self.s.device_type,
        })
        device_id = result["device_id"]
        self.state.set("device_id", device_id)
        return device_id


def push_queue(state: LocalState, client: FalseTechClient) -> dict[str, int]:
    events = state.unsent()
    if not events:
        return {"inserted": 0, "duplicates": 0, "received": 0}
    result = client.rpc("falsetech_sync_push", {"p_device_id": client.ensure_device(), "p_events": events})
    state.mark_sent([event["operation_id"] for event in events])
    return result


def pull_remote(state: LocalState, client: FalseTechClient) -> list[dict[str, Any]]:
    after = state.get("pull_after", "1970-01-01T00:00:00+00:00")
    result = client.rpc("falsetech_sync_pull", {"p_device_id": client.ensure_device(), "p_after": after, "p_limit": 500})
    if result:
        state.set("pull_after", max(event["created_at"] for event in result))
    return result


def scan_once(settings: Settings, state: LocalState, client: FalseTechClient) -> dict[str, int]:
    stats = {"seen": 0, "changed": 0, "renamed": 0, "duplicates": 0, "errors": 0}
    device_id = client.ensure_device()
    for original_path in iter_files(settings.scan_roots):
        try:
            stat = original_path.stat()
            stats["seen"] += 1
            if not state.file_changed(original_path, stat.st_size, stat.st_mtime_ns):
                continue
            current_path, rename_reason = safe_rename(original_path, settings.rename_roots)
            if current_path != original_path:
                stats["renamed"] += 1
            stat = current_path.stat()
            digest = sha256_file(current_path)
            project_label, project_key = project_for(current_path)
            result = client.rpc("falsetech_artifact_register", {
                "p_device_id": device_id,
                "p_project_key": project_key or "",
                "p_canonical_name": current_path.name,
                "p_original_name": original_path.name,
                "p_original_path": str(original_path),
                "p_content_hash": digest,
                "p_size_bytes": stat.st_size,
                "p_mime_type": mimetypes.guess_type(current_path.name)[0],
                "p_artifact_kind": kind_for(current_path),
                "p_rename_reason": rename_reason,
            })
            if result.get("duplicate"):
                stats["duplicates"] += 1
            state.upsert_file(current_path, digest, stat.st_size, stat.st_mtime_ns, current_path.name, original_path.name, project_key)
            state.enqueue("file_seen", project_key, {
                "canonical_name": current_path.name,
                "original_name": original_path.name,
                "original_path": str(original_path),
                "current_path": str(current_path),
                "content_hash": digest,
                "size_bytes": stat.st_size,
                "kind": kind_for(current_path),
                "project_label": project_label,
                "rename_reason": rename_reason,
                "duplicate": bool(result.get("duplicate")),
            }, "artifact", result.get("artifact_id"))
            stats["changed"] += 1
        except (PermissionError, FileNotFoundError, OSError):
            stats["errors"] += 1
    push_queue(state, client)
    return stats


def write_report(settings: Settings, label: str, payload: dict[str, Any]) -> Path:
    report_dir = settings.root / "Continuity" / "Reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    target = report_dir / f"{label}-{settings.device_name}-{datetime.now().strftime('%Y-%m-%d-%H%M%S')}.json"
    target.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return target


def doctor(settings: Settings, state: LocalState, client: FalseTechClient) -> dict[str, Any]:
    report: dict[str, Any] = {
        "device_name": settings.device_name,
        "hostname": socket.gethostname(),
        "local_database": str(state.path),
        "scan_roots": [{"path": str(path), "exists": path.exists()} for path in settings.scan_roots],
        "timestamp": utc_now(),
    }
    try:
        client.login()
        report["workspace"] = client.rpc("falsetech_workspace", {})
        report["device_id"] = client.ensure_device()
        report["sync_push"] = push_queue(state, client)
        report["sync_pull_count"] = len(pull_remote(state, client))
        report["status"] = "healthy"
    except Exception as exc:
        report["status"] = "error"
        report["error"] = str(exc)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="FalseTech set-and-forget continuity node")
    parser.add_argument("--config", default=os.getenv("FALSETECH_NODE_CONFIG", r"C:\FalseTech\System\FalseTech-Node.json"))
    parser.add_argument("--login", action="store_true")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--doctor", action="store_true")
    parser.add_argument("--context", metavar="PROJECT")
    args = parser.parse_args()

    settings = Settings(Path(args.config))
    state = LocalState(settings.db_path)
    client = FalseTechClient(settings, state)

    if args.login:
        client.login()
        print("FalseTech login stored in Windows Credential Manager.")
        return 0
    if args.context:
        client.login()
        print(json.dumps(client.rpc("falsetech_context", {"p_project": args.context}), indent=2))
        return 0
    if args.doctor:
        report = doctor(settings, state, client)
        print(json.dumps(report, indent=2))
        print(f"Report: {write_report(settings, 'FalseTech-Node-Health', report)}")
        return 0 if report.get("status") == "healthy" else 2

    client.login()
    if args.once or not args.watch:
        result = {"scan": scan_once(settings, state, client), "remote_events": len(pull_remote(state, client)), "timestamp": utc_now()}
        print(json.dumps(result, indent=2))
        print(f"Report: {write_report(settings, 'FalseTech-Node-Run', result)}")
        return 0

    while True:
        try:
            scan_once(settings, state, client)
            pull_remote(state, client)
        except Exception as exc:
            write_report(settings, "FalseTech-Node-Error", {"status": "error", "error": str(exc), "timestamp": utc_now()})
        time.sleep(settings.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
