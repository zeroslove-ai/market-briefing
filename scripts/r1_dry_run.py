#!/usr/bin/env python3
"""Small external-server smoke entrypoint for the R1 canonical data plane."""

from __future__ import annotations

import argparse
import json

from market_board import collect_market_board
from market_clock import get_market_clock
from report_snapshots import persist_report_snapshot
from state_store import atomic_write_json, state_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("morning", "evening", "open", "close"))
    args = parser.parse_args()
    clock = get_market_clock(args.phase)
    payload = {"meta": clock.as_dict(), "indicators": collect_market_board()["indicators"]}
    snapshot = persist_report_snapshot(clock.phase, payload, clock.market_session_date)
    atomic_write_json(state_path("market_snapshot_latest.json"), snapshot)
    print(json.dumps(snapshot, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

