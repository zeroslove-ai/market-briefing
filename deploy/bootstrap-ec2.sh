#!/usr/bin/env bash
set -euo pipefail

APP_DIR=/opt/market-briefing
sudo apt-get update
sudo apt-get install -y git python3 python3-venv ca-certificates
if [ ! -d "$APP_DIR/.git" ]; then
  sudo git clone --branch feature/hermes-r1-data-core https://github.com/zeroslove-ai/market-briefing.git "$APP_DIR"
fi
sudo chown -R ubuntu:ubuntu "$APP_DIR"
cd "$APP_DIR"
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
mkdir -p state/report_snapshots state/report_history state/option
python scripts/r1_dry_run.py --phase morning > /tmp/market-briefing-r1-dry-run.json
echo "R1 dry-run completed; canonical state is under $APP_DIR/state"
