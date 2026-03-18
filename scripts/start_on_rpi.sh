#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Probe RS-485/Modbus before starting server.
python tools/rs485_probe.py --slave "${MODBUS_SLAVE_ID:-0}" --baudrate "${MODBUS_BAUDRATE:-9600}" --retries "${MODBUS_RETRIES:-3}" || true

export SIMULATION_MODE="${SIMULATION_MODE:-0}"
export HOST="${HOST:-127.0.0.1}"
python app.py
