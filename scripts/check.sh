#!/usr/bin/env bash
# Alle lokalen Prüfungen in einem Lauf.
# Nutzung: PYTHON=/pfad/zu/venv/bin/python scripts/check.sh
set -euo pipefail

cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-python3}"

echo "== pytest =="
"$PYTHON" -m pytest -q

echo "== ruff lint =="
"$PYTHON" -m ruff check .

echo "== ruff format =="
"$PYTHON" -m ruff format --check .

echo "== yamllint =="
"$PYTHON" -m yamllint -c .yamllint .

echo "== Konfiguration =="
"$PYTHON" scripts/validate_config.py

echo "== pip-audit =="
if "$PYTHON" -m pip_audit --version >/dev/null 2>&1; then
  "$PYTHON" -m pip_audit -r requirements-dev.txt --progress-spinner off
else
  echo "Hinweis: pip-audit nicht installiert – wird in CI ausgeführt."
fi

echo "Alle Prüfungen erfolgreich."
