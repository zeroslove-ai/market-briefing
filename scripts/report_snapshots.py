"""Persist phase reports and deterministic changes-since-previous-report."""

from __future__ import annotations

import json
from datetime import date
from typing import Any, Optional

from state_store import atomic_write_json, read_json, state_path, utc_now_iso


def _metric(payload: dict, category: str, key: str, field: str = "change_pct"):
    try:
        return payload["indicators"][category][key].get(field)
    except (KeyError, TypeError, AttributeError):
        return None


def _legacy_metric(payload: dict, symbol: str, field: str):
    try:
        return payload["quotes"][symbol].get(field)
    except (KeyError, TypeError, AttributeError):
        return None


def extract_metrics(payload: dict) -> dict:
    return {
        "NQ_change_pct": _metric(payload, "futures", "nq") if "indicators" in payload else _legacy_metric(payload, "NQ=F", "change_pct"),
        "VIX": _metric(payload, "volatility", "vix", "price") if "indicators" in payload else _legacy_metric(payload, "^VIX", "price"),
        "TNX": _metric(payload, "rates", "us10y", "price") if "indicators" in payload else _legacy_metric(payload, "^TNX", "price"),
        "BTC_24h_change_pct": _metric(payload, "crypto", "btc") if "indicators" in payload else None,
        "sigma_lower_break_count": payload.get("sigma", {}).get("market_summary", {}).get("lower_break_count"),
    }


def _latest_prior(current_phase: str) -> Optional[dict]:
    candidates = []
    for path in state_path("report_snapshots").glob("latest_*.json"):
        if path.stem == f"latest_{current_phase}":
            continue
        document = read_json(path)
        if document:
            candidates.append(document)
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.get("generated_at", ""))


def compute_changes(current: dict, previous: Optional[dict]) -> dict:
    if not previous:
        return {}
    current_metrics = extract_metrics(current)
    previous_metrics = extract_metrics(previous)
    changes = {}
    for key, value in current_metrics.items():
        prior = previous_metrics.get(key)
        if isinstance(value, (int, float)) and isinstance(prior, (int, float)):
            changes[key] = round(value - prior, 6)
    return changes


def persist_report_snapshot(phase: str, payload: dict, session_date: date | str) -> dict:
    previous = _latest_prior(phase)
    document = dict(payload)
    document["schema_version"] = 1
    document["generated_at"] = utc_now_iso()
    document["session_date"] = session_date.isoformat() if isinstance(session_date, date) else session_date
    document["phase"] = phase
    document["changes_since_previous_report"] = compute_changes(payload, previous)
    latest_path = state_path("report_snapshots", f"latest_{phase}.json")
    atomic_write_json(latest_path, document)
    history_path = state_path("report_history", f"{document['session_date']}.jsonl")
    with history_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(document, ensure_ascii=False, sort_keys=True) + "\n")
    return document

