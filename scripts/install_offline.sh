#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${PROJECT_DIR}/.venv_portable"
WHEEL_DIR="${PROJECT_DIR}/third_party/wheels"

if [[ ! -d "${WHEEL_DIR}" ]]; then
  echo "Offline wheel bundle missing at ${WHEEL_DIR}."
  echo "Prepare it using scripts/build_offline_bundle.sh on a machine with internet."
  exit 1
fi

python3 -m venv "${VENV_DIR}"
source "${VENV_DIR}/bin/activate"

python -m pip install --no-index --find-links "${WHEEL_DIR}" -r "${PROJECT_DIR}/requirements.txt"
python -m pip install --no-index --find-links "${WHEEL_DIR}" gunicorn || true

echo "Offline install completed in ${VENV_DIR}."
