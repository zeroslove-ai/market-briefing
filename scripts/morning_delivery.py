#!/usr/bin/env python3
"""Build one 06:30 KST morning artifact and optionally deliver Email + Telegram."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, time
from pathlib import Path

from delivery_adapters import send_gmail_smtp, send_telegram
from delivery_render import render_email_full, render_telegram_compact
from market_board import collect_market_board
from market_clock import KST, last_actual_regular_session, next_regular_session, now_kst
from market_data import RunCache
from state_store import atomic_write_json, read_json, state_path, utc_now_iso
from us_market_report import collect_earnings, collect_econ, collect_news


MORNING_START = time(6, 30)
MORNING_CATCHUP_UNTIL = time(8, 0)


def delivery_mode(now: datetime) -> str:
    local = now.astimezone(KST)
    if local.weekday() == 6:
        return "skip"
    if local.weekday() == 0:
        return "week_kickoff"
    return "close_autopsy"


def within_delivery_window(now: datetime) -> bool:
    local = now.astimezone(KST).time()
    return MORNING_START <= local <= MORNING_CATCHUP_UNTIL


def build_morning_payload(now: datetime | None = None) -> dict:
    now = now or datetime.now(tz=KST)
    local = now.astimezone(KST)
    mode = delivery_mode(local)
    completed_session = last_actual_regular_session(local)
    upcoming_session = next_regular_session(completed_session)
    cache = RunCache()
    board = collect_market_board(cache)
    previous_close = read_json(state_path("report_snapshots", "latest_close.json"), {}) or {}

    econ = collect_econ()
    econ_errors = [item.get("error") for item in econ if isinstance(item, dict) and item.get("error")]
    payload = {
        "schema_version": 1,
        "generated_at": utc_now_iso(),
        "session_date": completed_session.isoformat(),
        "delivery": {
            "mode": mode,
            "delivery_date": local.date().isoformat(),
            "scheduled_cutoff_at_kst": datetime.combine(local.date(), MORNING_START, tzinfo=KST).isoformat(),
            "generated_at_kst": local.isoformat(),
            "upcoming_us_session": upcoming_session.isoformat(),
        },
        "indicators": board.get("indicators", {}),
        "news": collect_news(),
        "econ_calendar": econ,
        "earnings": collect_earnings(upcoming_session),
        "options": previous_close.get("options", {}),
        "data_quality": list(board.get("data_quality", [])) + [f"econ_calendar: {error}" for error in econ_errors],
    }
    return payload


def _artifact_dir(payload: dict) -> Path:
    base = state_path("delivery", "artifacts", payload["delivery"]["delivery_date"])
    base.mkdir(parents=True, exist_ok=True)
    return base


def write_artifacts(payload: dict) -> dict:
    subject, plain, html = render_email_full(payload)
    telegram_messages = render_telegram_compact(payload)
    base = _artifact_dir(payload)
    mode = payload["delivery"]["mode"]
    paths = {
        "payload": base / f"{mode}-payload.json",
        "email_plain": base / f"{mode}-email.txt",
        "email_html": base / f"{mode}-email.html",
        "telegram": base / f"{mode}-telegram.txt",
    }
    atomic_write_json(paths["payload"], payload)
    paths["email_plain"].write_text(plain + "\n", encoding="utf-8")
    paths["email_html"].write_text(html + "\n", encoding="utf-8")
    paths["telegram"].write_text("\n\n--- MESSAGE BREAK ---\n\n".join(telegram_messages) + "\n", encoding="utf-8")
    return {"subject": subject, "plain": plain, "html": html, "telegram": telegram_messages, "paths": {k: str(v) for k, v in paths.items()}}


def _ledger() -> tuple[Path, dict]:
    path = state_path("delivery", "ledger.json")
    return path, read_json(path, {"schema_version": 1, "deliveries": {}}) or {"schema_version": 1, "deliveries": {}}


def _delivery_key(payload: dict, channel: str) -> str:
    meta = payload["delivery"]
    return f"{meta['delivery_date']}:{meta['mode']}:{channel}"


def already_sent(payload: dict, channel: str) -> bool:
    _, ledger = _ledger()
    return ledger.get("deliveries", {}).get(_delivery_key(payload, channel), {}).get("status") == "sent"


def mark_delivery(payload: dict, channel: str, status: str, detail: str = "") -> None:
    path, ledger = _ledger()
    deliveries = dict(ledger.get("deliveries", {}))
    deliveries[_delivery_key(payload, channel)] = {
        "status": status,
        "updated_at": utc_now_iso(),
        "detail": detail[:500],
    }
    atomic_write_json(path, {"schema_version": 1, "generated_at": utc_now_iso(), "deliveries": deliveries})


def _recipients(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def deliver(payload: dict, rendered: dict, *, force: bool = False) -> dict:
    results = {}
    if not force and already_sent(payload, "telegram"):
        results["telegram"] = "already_sent"
    else:
        try:
            send_telegram(
                rendered["telegram"],
                bot_token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
                chat_id=os.environ.get("TELEGRAM_CHAT_ID", ""),
                thread_id=os.environ.get("TELEGRAM_MESSAGE_THREAD_ID") or None,
            )
            mark_delivery(payload, "telegram", "sent")
            results["telegram"] = "sent"
        except Exception as error:
            mark_delivery(payload, "telegram", "failed", str(error))
            results["telegram"] = f"failed: {error}"

    if not force and already_sent(payload, "email"):
        results["email"] = "already_sent"
    else:
        try:
            send_gmail_smtp(
                subject=rendered["subject"],
                plain=rendered["plain"],
                html=rendered["html"],
                smtp_user=os.environ.get("GMAIL_SMTP_USER", ""),
                app_password=os.environ.get("GMAIL_APP_PASSWORD", ""),
                recipients=_recipients(os.environ.get("EMAIL_TO", "")),
                sender=os.environ.get("EMAIL_FROM") or None,
            )
            mark_delivery(payload, "email", "sent")
            results["email"] = "sent"
        except Exception as error:
            mark_delivery(payload, "email", "failed", str(error))
            results["email"] = f"failed: {error}"
    return results


def parse_now(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("--now requires an offset-aware ISO timestamp")
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--send", action="store_true", help="Actually deliver; default is artifact-only dry-run.")
    parser.add_argument("--force", action="store_true", help="Override delivery ledger duplicate protection.")
    parser.add_argument("--now", help="Offset-aware ISO timestamp for testing.")
    args = parser.parse_args()
    now = parse_now(args.now) or datetime.now(tz=KST)
    mode = delivery_mode(now)
    if mode == "skip":
        print(json.dumps({"status": "skipped", "reason": "sunday_delivery_disabled"}, ensure_ascii=False))
        return 0
    if not within_delivery_window(now) and not args.force:
        print(json.dumps({"status": "skipped", "reason": "outside_0630_0800_kst_window"}, ensure_ascii=False))
        return 0

    payload = build_morning_payload(now)
    rendered = write_artifacts(payload)
    result = {
        "status": "rendered",
        "mode": payload["delivery"]["mode"],
        "delivery_date": payload["delivery"]["delivery_date"],
        "artifacts": rendered["paths"],
        "telegram_messages": len(rendered["telegram"]),
    }
    if args.send:
        result["delivery"] = deliver(payload, rendered, force=args.force)
        if any(str(value).startswith("failed:") for value in result["delivery"].values()):
            result["status"] = "partial_failure"
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 2
        result["status"] = "sent"
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
