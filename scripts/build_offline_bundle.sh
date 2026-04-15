#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WHEEL_DIR="${PROJECT_DIR}/third_party/wheels"

mkdir -p "${WHEEL_DIR}"
python3 -m pip download --dest "${WHEEL_DIR}" -r "${PROJECT_DIR}/requirements.txt"
python3 -m pip download --dest "${WHEEL_DIR}" gunicorn

echo "Offline bundle prepared in ${WHEEL_DIR}."
