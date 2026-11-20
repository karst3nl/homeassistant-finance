# Entwicklung

## Aufbau

- `addons/finance/app/main.py` – Starlette-App, Middlewares, Lifespan
- `addons/finance/app/db.py` – SQLite-Verbindungen und Migrationen
- `addons/finance/app/api/` – interne CRUD-Endpunkte
- `addons/finance/app/ui.py` – servergerenderte Oberfläche
- `addons/finance/app/stats.py`, `reports.py`, `charts.py` – Auswertungen und SVG-Charts
- `tests/` – pytest-Integrationstests gegen temporäre Datenbanken

Ein Prozess, eine Datenbankdatei, keine JavaScript-Build-Tools. Laufzeit-Abhängigkeiten sind in `requirements-dev.txt` identisch zum Dockerfile gepinnt.

## Lokal starten

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt

FINANCE_DB_PATH=/tmp/finance.db FINANCE_RESTRICT_INGRESS=0 \
  uvicorn main:app --app-dir addons/finance/app --reload --port 8099
```

Die IP-Sperre ist für lokale Entwicklung deaktiviert; im Container ist sie aktiv.

## Prüfungen

```bash
pytest -q
ruff check .
ruff format --check .
yamllint -c .yamllint .
python scripts/validate_config.py

# alles in einem Lauf (pip-audit nur wenn installiert):
PYTHON="$PWD/.venv/bin/python" scripts/check.sh
```

Optional: `python scripts/bench.py` misst die Oberfläche gegen 500 Beispielbuchungen (siehe [performance.md](performance.md)).

## Migrationen

Neue SQL-Dateien in `addons/finance/app/migrations/` mit aufsteigender Nummer (`002_...sql`) anlegen. `init_db()` liest `PRAGMA user_version` und wendet alle neueren Migrationen beim Start an. Bestehende Datenbanken werden nicht gelöscht.

## Release

1. Änderungen und Tests auf `main` mergen.
2. Version in `addons/finance/config.yaml` und `pyproject.toml` erhöhen, `CHANGELOG.md` ergänzen.
3. GitHub Release `vX.Y.Z` publizieren. `release.yaml` baut `aarch64`/`amd64`, pusht nach GHCR und veröffentlicht das signierte Multi-Arch-Manifest.
4. GHCR-Paket beim ersten Mal explizit public setzen.
5. Die finale Repository-URL (`karst3nl/homeassistant-finance`) steht bereits in `repository.yaml`, `config.yaml`, Badge und Add-on-README. Sie nach dem ersten Push nicht mehr ändern.

Die Add-on-ID wird aus der Repository-URL abgeleitet. Die URL nach dem ersten Veröffentlichen nicht mehr ändern.
