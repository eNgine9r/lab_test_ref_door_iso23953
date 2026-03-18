#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

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
    print('ok')
except Exception:
    raise SystemExit(1)
PY
  then
    break
  fi
  sleep 1
done

open_browser "$URL" || echo "Open the web interface manually: $URL"
wait "$APP_PID"
