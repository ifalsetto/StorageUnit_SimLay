from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CANONICAL_REPOSITORY = "ifalsetto/StorageUnit_SimLay"
CANONICAL_REMOTE_TOKENS = (
    "github.com/ifalsetto/storageunit_simlay",
    "github.com:ifalsetto/storageunit_simlay",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _git_remote(repo: Path) -> str | None:
    if not (repo / ".git").exists():
        return None
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "remote", "get-url", "origin"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = result.stdout.strip()
    return value or None


def _is_canonical_remote(remote: str | None) -> bool:
    normalized = (remote or "").lower().removesuffix(".git")
    return any(token in normalized for token in CANONICAL_REMOTE_TOKENS)


def _candidate_role(repo: Path) -> str:
    role_path = repo / "FALSETECH_REPOSITORY_ROLE.md"
    if not role_path.exists():
        return "unknown"
    text = role_path.read_text(encoding="utf-8", errors="ignore").lower()
    if "not the simlay core" in text and "wix" in text:
        return "wix_storefront_adapter"
    if "canonical simlay core" in text:
        return "declared_canonical"
    return "documented_other"


def _scan_active_simlay_repos(false_tech_root: Path, current_root: Path) -> list[dict[str, Any]]:
    projects_root = false_tech_root / "Projects"
    if not projects_root.exists():
        return []
    candidates: list[dict[str, Any]] = []
    skip_names = {"node_modules", ".venv", "venv", "dist", "build", ".git", "__pycache__"}
    for directory, child_dirs, _ in os.walk(projects_root):
        child_dirs[:] = [name for name in child_dirs if name not in skip_names]
        repo = Path(directory)
        if not (repo / ".git").exists():
            continue
        child_dirs[:] = []
        remote = _git_remote(repo)
        identity = f"{repo.name} {remote or ''}".lower()
        if "simlay" not in identity and "storageunit" not in identity and "storage-unit" not in identity:
            continue
        candidates.append(
            {
                "path": str(repo),
                "remote": remote,
                "role": _candidate_role(repo),
                "is_current": repo.resolve() == current_root.resolve(),
                "is_canonical_remote": _is_canonical_remote(remote),
            }
        )
    return candidates


def check_runtime_continuity(*, strict: bool | None = None) -> dict[str, Any]:
    root = _repo_root()
    strict = strict if strict is not None else os.getenv("SIMLAY_CONTINUITY_STRICT", "0") == "1"
    errors: list[str] = []
    warnings: list[str] = []

    agents_path = root / "AGENTS.md"
    agents_text = agents_path.read_text(encoding="utf-8", errors="ignore") if agents_path.exists() else ""
    if CANONICAL_REPOSITORY not in agents_text:
        errors.append("Canonical lineage marker is missing from AGENTS.md")

    remote = _git_remote(root)
    if remote and not _is_canonical_remote(remote):
        errors.append(f"Current checkout origin is not canonical: {remote}")
    if not remote:
        warnings.append("Git metadata is unavailable; canonical remote could not be verified at runtime.")

    configured_root = os.getenv("FALSETECH_ROOT")
    false_tech_root = Path(configured_root) if configured_root else Path("C:/FalseTech")
    candidates = _scan_active_simlay_repos(false_tech_root, root) if false_tech_root.exists() else []
    duplicate_core_candidates = [
        candidate
        for candidate in candidates
        if not candidate["is_current"]
        and not candidate["is_canonical_remote"]
        and candidate["role"] != "wix_storefront_adapter"
    ]
    if duplicate_core_candidates:
        errors.append(
            "Potential parallel SimLay core checkout(s) found under FalseTech Projects: "
            + ", ".join(candidate["path"] for candidate in duplicate_core_candidates)
        )

    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "canonical_repository": CANONICAL_REPOSITORY,
        "current_root": str(root),
        "current_remote": remote,
        "strict": strict,
        "candidates": candidates,
        "errors": errors,
        "warnings": warnings,
        "passed": not errors,
    }

    report_path = root / "backend" / "data" / "continuity_last_check.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    except OSError:
        warnings.append("Continuity report could not be written to backend/data.")

    if strict and errors:
        raise RuntimeError("SimLay continuity gate failed: " + " | ".join(errors))
    return report
