#!/usr/bin/env bash
set -euo pipefail

APP_DIR=/opt/market-briefing
APP_USER=${SUDO_USER:-${USER:-ubuntu}}
sudo apt-get update
sudo apt-get install -y git python3 python3-venv ca-certificates
if [ ! -d "$APP_DIR/.git" ]; then
  sudo git clone --branch feature/hermes-r1-data-core https://github.com/zeroslove-ai/market-briefing.git "$APP_DIR"
fi
sudo chown -R "$APP_USER:$APP_USER" "$APP_DIR"
cd "$APP_DIR"
sudo -u "$APP_USER" python3 -m venv .venv
sudo -u "$APP_USER" .venv/bin/python -m pip install --upgrade pip
sudo -u "$APP_USER" .venv/bin/python -m pip install -r requirements.txt
sudo -u "$APP_USER" mkdir -p state/report_snapshots state/report_history state/option
sudo -u "$APP_USER" .venv/bin/python scripts/r1_dry_run.py --phase morning > /tmp/market-briefing-r1-dry-run.json
echo "R1 dry-run completed; canonical state is under $APP_DIR/state"
