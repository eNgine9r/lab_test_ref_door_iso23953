#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

VENV_DIR="${PROJECT_DIR}/.venv_portable"
WHEEL_DIR="${PROJECT_DIR}/third_party/wheels"

if [[ ! -d "$VENV_DIR" ]]; then
  python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"

if [[ "${OFFLINE_MODE:-1}" == "1" ]]; then
  if [[ -d "$WHEEL_DIR" ]]; then
    python -m pip install --no-index --find-links "$WHEEL_DIR" -r requirements.txt
  else
    echo "Offline mode requested, but ${WHEEL_DIR} not found."
    echo "Run scripts/build_offline_bundle.sh once on an online machine and copy third_party/wheels."
    exit 1
  fi
else
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt
fi

export SIMULATION_MODE="${SIMULATION_MODE:-0}"
export HOST="${HOST:-127.0.0.1}"
export PORT="${PORT:-5000}"
export AUTO_OPEN_BROWSER="${AUTO_OPEN_BROWSER:-1}"
export MODBUS_BACKEND="${MODBUS_BACKEND:-auto}"

if [[ -e /dev/ttyUSB0 ]]; then
  export MODBUS_PORT="${MODBUS_PORT:-/dev/ttyUSB0}"
fi

export URL="http://${HOST}:${PORT}/"

open_browser() {
  local url="$1"
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$url" >/dev/null 2>&1 &
    return 0
  fi
  if command -v chromium-browser >/dev/null 2>&1; then
    chromium-browser "$url" >/dev/null 2>&1 &
    return 0
  fi
  if command -v chromium >/dev/null 2>&1; then
    chromium "$url" >/dev/null 2>&1 &
    return 0
  fi
  return 1
}

python app.py "$@" &
APP_PID=$!

for _ in {1..30}; do
  if python - <<'PY'
import os
import urllib.request
url = os.environ['URL']
try:
    urllib.request.urlopen(url, timeout=1)
except Exception:
    raise SystemExit(1)
PY
  then
    break
  fi
  sleep 1
done

if [[ "${AUTO_OPEN_BROWSER}" == "1" ]]; then
  open_browser "$URL" || echo "Open the web interface manually: $URL"
fi

wait "$APP_PID"
