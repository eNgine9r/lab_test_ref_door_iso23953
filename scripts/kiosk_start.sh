#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

export HOST="${HOST:-127.0.0.1}"
export PORT="${PORT:-5000}"
export URL="http://${HOST}:${PORT}/"

./scripts/rotate_screen.sh || true
./scripts/start_on_rpi.sh &
APP_PID=$!

for _ in {1..60}; do
  if curl -fsS "$URL/status" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if command -v chromium-browser >/dev/null 2>&1; then
  chromium-browser --kiosk --noerrdialogs --disable-infobars --incognito "$URL" >/dev/null 2>&1 &
elif command -v chromium >/dev/null 2>&1; then
  chromium --kiosk --noerrdialogs --disable-infobars --incognito "$URL" >/dev/null 2>&1 &
fi

wait "$APP_PID"
