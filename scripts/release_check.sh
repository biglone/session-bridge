#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ -x "${ROOT_DIR}/.venv/bin/python" ]]; then
  PY_BIN="${ROOT_DIR}/.venv/bin/python"
else
  python3 -m venv .venv
  PY_BIN="${ROOT_DIR}/.venv/bin/python"
fi

"${PY_BIN}" -m pip install --upgrade pip
"${PY_BIN}" -m pip install -e . pytest build twine

PYTHONPATH=src "${PY_BIN}" -m pytest -q
"${PY_BIN}" -m build --sdist --wheel
"${PY_BIN}" -m twine check dist/*
npm pack --dry-run

echo "release-check: ok"
