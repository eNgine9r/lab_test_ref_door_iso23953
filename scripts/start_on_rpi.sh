#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install minimalmodbus

export SIMULATION_MODE="${SIMULATION_MODE:-0}"
export HOST="${HOST:-127.0.0.1}"
export MODBUS_BACKEND="${MODBUS_BACKEND:-auto}"

# Prefer a known USB adapter port if present.
if [[ -e /dev/ttyUSB0 ]]; then
  export MODBUS_PORT="${MODBUS_PORT:-/dev/ttyUSB0}"
fi

# Diagnostics before startup.
python tools/rs485_probe.py --slave "${MODBUS_SLAVE_ID:-0}" --baudrate "${MODBUS_BAUDRATE:-9600}" --port "${MODBUS_PORT:-}" --retries "${MODBUS_RETRIES:-3}" || true
python tools/serial_port_test.py --port "${MODBUS_PORT:-/dev/ttyUSB0}" || true

python app.py
