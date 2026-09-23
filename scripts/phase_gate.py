"""Timezone-aware, holiday-aware scheduler gate with per-session idempotency."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, time, timezone
from pathlib import Path

from market_clock import ET, KST, is_regular_session_day
from state_store import atomic_write_json, read_json, state_path, utc_now_iso

SCHEDULE = {
    "morning": (KST, time(6, 30)),
    "evening": (KST, time(21, 0)),
    "open": (ET, time(9, 30)),
    "close": (ET, time(16, 5)),
}
ON_TIME_GRACE = 120
MORNING_CATCHUP_UNTIL = time(8, 0)
EVENING_MAX_CATCHUP = 2 * 60 * 60


def delivery_decision(phase: str, now: datetime) -> dict:
    """Resolve eligibility and the report key before touching idempotency state."""
    if phase not in SCHEDULE or now.tzinfo is None:
        return {"eligible": False, "reason": "unknown_phase_or_naive_datetime", "session_date": None}
    zone, scheduled_time = SCHEDULE[phase]
    local = now.astimezone(zone)
    target = datetime.combine(local.date(), scheduled_time, tzinfo=zone)
    session_date = local.date()

    if phase == "morning":
        kst_now = now.astimezone(KST)
        et_now = now.astimezone(ET)
        if not (scheduled_time <= kst_now.time() <= MORNING_CATCHUP_UNTIL):
            return {"eligible": False, "reason": "outside_morning_delivery_window", "session_date": None}
        # A morning report is only due when the ET calendar date itself was a
        # regular session and that session has closed. This rejects Sunday and
        # Monday KST runs instead of letting them claim Friday's report key.
        if not is_regular_session_day(et_now.date()) or et_now.time() < time(16, 0):
            return {"eligible": False, "reason": "no_newly_completed_us_session", "session_date": None}
        session_date = et_now.date()
    elif phase == "evening":
        kst_now = now.astimezone(KST)
        et_now = now.astimezone(ET)
        if kst_now.weekday() >= 5:
            return {"eligible": False, "reason": "weekend_delivery_day", "session_date": None}
        if not is_regular_session_day(et_now.date()):
            return {"eligible": False, "reason": "no_us_session_on_delivery_day", "session_date": None}
        # Persistent timers may recover after a reboot, but only before this
        # session opens and no more than two hours after the 21:00 KST target.
        latest = min(target.timestamp() + EVENING_MAX_CATCHUP, datetime.combine(
            et_now.date(), time(9, 30), tzinfo=ET
        ).timestamp())
        if now.timestamp() < target.timestamp() or now.timestamp() >= latest:
            return {"eligible": False, "reason": "outside_evening_catchup_window", "session_date": None}
        session_date = et_now.date()
    else:
        if not is_regular_session_day(local.date()):
            return {"eligible": False, "reason": "us_market_closed", "session_date": None}
        delta = (local - target).total_seconds()
        if abs(delta) > ON_TIME_GRACE:
            return {"eligible": False, "reason": "outside_phase_window", "session_date": None}

    late = now.timestamp() - target.timestamp() > ON_TIME_GRACE
    return {
        "eligible": True,
        "reason": "eligible",
        "session_date": session_date.isoformat(),
        "delivery_status": "catchup" if late else "on_time",
        "late": late,
        "catchup": late,
        "scheduled_at": target.isoformat(),
        "executed_at": local.isoformat(),
    }


def is_phase_due(phase: str, now: datetime, tolerance_seconds: int = ON_TIME_GRACE) -> bool:
    """Compatibility boolean API; delivery policy is centralized above."""
    if tolerance_seconds != ON_TIME_GRACE and phase in {"open", "close"}:
        zone, scheduled_time = SCHEDULE[phase]
        local = now.astimezone(zone)
        target = datetime.combine(local.date(), scheduled_time, tzinfo=zone)
        return (is_regular_session_day(local.date())
                and abs((local - target).total_seconds()) <= tolerance_seconds)
    return delivery_decision(phase, now).get("eligible", False)


def run_phase(phase: str, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    decision = delivery_decision(phase, now)
    if not decision["eligible"]:
        print(json.dumps({"status": "skipped", "reason": decision["reason"], "phase": phase}))
        return 0
    marker = state_path("scheduler", "phase_runs.json")
    state = read_json(marker, {}) or {}
    session_date = decision["session_date"]
    key = f"{phase}:{session_date}"
    if key in state.get("runs", {}):
        print(json.dumps({"status": "skipped", "reason": "already_completed", "key": key}))
        return 0

    script = Path(__file__).resolve().with_name("r1_dry_run.py")
    result = subprocess.run([sys.executable, str(script), "--phase", phase], check=False)
    if result.returncode:
        return result.returncode
    runs = dict(state.get("runs", {}))
    runs[key] = {
        "completed_at": utc_now_iso(),
        "session_date": session_date,
        "delivery_status": decision["delivery_status"],
        "late": decision["late"],
        "catchup": decision["catchup"],
        "scheduled_at": decision["scheduled_at"],
        "executed_at": decision["executed_at"],
    }
    atomic_write_json(marker, {"schema_version": 1, "generated_at": utc_now_iso(), "runs": runs})
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True, choices=tuple(SCHEDULE))
    args = parser.parse_args()
    return run_phase(args.phase)


if __name__ == "__main__":
    raise SystemExit(main())
