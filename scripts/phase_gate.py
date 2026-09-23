"""Timezone-aware, holiday-aware scheduler gate with per-session idempotency."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, time, timezone
from pathlib import Path

from market_clock import ET, KST, get_market_clock, is_regular_session_day
from state_store import atomic_write_json, read_json, state_path, utc_now_iso

SCHEDULE = {
    "morning": (KST, time(6, 30)),
    "evening": (KST, time(21, 0)),
    "open": (ET, time(9, 30)),
    "close": (ET, time(16, 5)),
}


def is_phase_due(phase: str, now: datetime, tolerance_seconds: int = 120) -> bool:
    """Return true only near the intended wall-clock time and valid US session."""
    if phase not in SCHEDULE or now.tzinfo is None:
        return False
    zone, scheduled_time = SCHEDULE[phase]
    local = now.astimezone(zone)
    if phase in {"open", "close"} and not is_regular_session_day(local.date()):
        return False
    target = datetime.combine(local.date(), scheduled_time, tzinfo=zone)
    delta = abs((local - target).total_seconds())
    return delta <= tolerance_seconds


def run_phase(phase: str, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    if not is_phase_due(phase, now):
        print(json.dumps({"status": "skipped", "reason": "outside_phase_window_or_market_closed", "phase": phase}))
        return 0
    clock = get_market_clock(phase, now)
    marker = state_path("scheduler", "phase_runs.json")
    state = read_json(marker, {}) or {}
    key = f"{phase}:{clock.market_session_date.isoformat()}"
    if key in state.get("runs", {}):
        print(json.dumps({"status": "skipped", "reason": "already_completed", "key": key}))
        return 0

    script = Path(__file__).resolve().with_name("r1_dry_run.py")
    result = subprocess.run([sys.executable, str(script), "--phase", phase], check=False)
    if result.returncode:
        return result.returncode
    runs = dict(state.get("runs", {}))
    runs[key] = {"completed_at": utc_now_iso(), "session_date": clock.market_session_date.isoformat()}
    atomic_write_json(marker, {"schema_version": 1, "generated_at": utc_now_iso(), "runs": runs})
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True, choices=tuple(SCHEDULE))
    args = parser.parse_args()
    return run_phase(args.phase)


if __name__ == "__main__":
    raise SystemExit(main())
