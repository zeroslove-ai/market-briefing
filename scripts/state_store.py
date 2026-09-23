"""Repository-root state paths and atomic JSON persistence."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

SCHEMA_VERSION = 1
REPO_ROOT = Path(__file__).resolve().parents[1]
STATE_ROOT = REPO_ROOT / "state"


def state_path(*parts: str) -> Path:
    path = STATE_ROOT.joinpath(*parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path, default: Any = None) -> Any:
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError, TypeError):
        return default


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def state_document(payload: Any, session_date: Optional[date | str], source: str) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now_iso(),
        "session_date": session_date.isoformat() if isinstance(session_date, date) else session_date,
        "source": source,
        "data": payload,
    }


def _session_string(session_date: Optional[date | str]) -> Optional[str]:
    return session_date.isoformat() if isinstance(session_date, date) else session_date


def load_oi_baseline(session_date: Optional[date | str] = None) -> dict:
    """Read the close-owned OI baseline without mutating it.

    ``snapshots`` is always the last committed close. If a close is rerun for
    the same session, ``previous_snapshots`` preserves the prior-session
    baseline so the rerun cannot redefine its own comparison point.
    """
    path = state_path("option", "oi_close_snapshot.json")
    document = read_json(path)
    if document is None:
        # Prior option-flow releases used this full-universe baseline. Keep it
        # read-only here: only the option-flow close job owns baseline writes.
        document = next((candidate for candidate in (
            read_json(STATE_ROOT / "flow_oi_snapshot.json"),
            read_json(REPO_ROOT / "scripts" / "flow_oi_snapshot.json"),
            read_json(STATE_ROOT / "oi_snapshot.json"),
            read_json(REPO_ROOT / "scripts" / "oi_snapshot.json"),
        ) if isinstance(candidate, dict) and candidate), {})
    if "data" in document and isinstance(document["data"], dict):
        document = document["data"]
    snapshots = document.get("snapshots")
    if not isinstance(snapshots, dict):
        snapshots = {key: value for key, value in document.items()
                     if isinstance(value, dict) and any(k in value for k in ("call_oi", "put_oi", "total_oi"))}
    # Older wrappers sometimes called the payload `data`.
    if not snapshots and isinstance(document.get("data"), dict):
        snapshots = document["data"]
    if "snapshots" in document:
        if session_date is not None and document.get("session_date") == _session_string(session_date):
            return {"session_date": document.get("previous_session_date"), "snapshots": document.get("previous_snapshots", {})}
        return {"session_date": document.get("session_date"), "snapshots": snapshots}
    return {"session_date": document.get("session_date") or document.get("date"), "snapshots": snapshots}


def load_flow_signals() -> dict:
    """Load current signals, migrating known legacy locations into state/option."""
    canonical = state_path("option", "flow_signals.json")
    document = read_json(canonical)
    if isinstance(document, dict):
        return document
    legacy = next((candidate for candidate in (
        read_json(STATE_ROOT / "flow_signals.json"),
        read_json(REPO_ROOT / "scripts" / "flow_signals.json"),
    ) if isinstance(candidate, dict)), {})
    if legacy:
        migrated = dict(legacy)
        migrated.setdefault("schema_version", SCHEMA_VERSION)
        migrated.setdefault("generated_at", utc_now_iso())
        migrated.setdefault("session_date", legacy.get("date"))
        atomic_write_json(canonical, migrated)
        return migrated
    return {}


def commit_oi_close(session_date: date | str, snapshots: dict, *, owner: str) -> dict:
    """Commit one close snapshot; same-session commits keep the old baseline."""
    if owner != "option_flow_close":
        raise PermissionError("OI baseline writes are owned by option_flow close only")
    path = state_path("option", "oi_close_snapshot.json")
    existing = read_json(path, {}) or {}
    existing_data = existing.get("data", existing) if isinstance(existing, dict) else {}
    current_date = _session_string(session_date)
    same_session = existing_data.get("session_date") == current_date
    previous_snapshots = existing_data.get("previous_snapshots", {}) if same_session else existing_data.get("snapshots", {})
    previous_date = existing_data.get("previous_session_date") if same_session else existing_data.get("session_date")
    document = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now_iso(),
        "session_date": current_date,
        "previous_session_date": previous_date,
        "source": "cboe-close",
        "snapshots": snapshots,
        "previous_snapshots": previous_snapshots,
    }
    atomic_write_json(path, document)
    return document
