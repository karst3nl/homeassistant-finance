# Home Assistant Finance

[![Open your Home Assistant instance and show the add app repository dialog with a specific repository URL pre-filled.](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fkarst3nl%2Fhomeassistant-finance)

Ein schlankes, vollständig lokales Home-Assistant-Add-on für persönliche Finanzen. Kein Cloud-Konto, keine Bankverbindung, keine zusätzlichen Add-ons – nur ein Webserver-Prozess, eine SQLite-Datei und eine Oberfläche in Home Assistant.

> **Status:** Phase 0–3 umgesetzt, Phase 4 (Härtung, Doku, Release-CI) lokal abgeschlossen. Version **0.9.0** ist der Release-Kandidat für v1.0. Die Repository-URL ist auf `karst3nl/homeassistant-finance` festgelegt; offen sind erster Push, GHCR-Veröffentlichung und der manuelle Pi-4-Smoketest. Plan: [ROADMAP.md](ROADMAP.md).

## Umfang in v1

- Konten und Kategorien verwalten
- Buchungen manuell erfassen, bearbeiten und löschen
- Budgets pro Kategorie und Monat
- Übersicht mit Saldo, Monatsausgaben und SVG-Charts
- 100 % lokal, Ingress-UI ohne eigene Ports und ohne eigenes Login
- Keine HA-Entitäten, kein MQTT, kein Zugriff auf die HA-API

## Installation

Nach der Veröffentlichung:

1. In Home Assistant: **Einstellungen → Apps → App installieren → Repositories**
2. URL eintragen: `https://github.com/karst3nl/homeassistant-finance`
3. Add-on **Finance** installieren und starten
4. Sidebar-Eintrag **Finanzen** öffnen

Das Image wird für `aarch64` und `amd64` aus GHCR geladen; ein lokaler Build ist nicht nötig. Der My-Home-Assistant-Badge oben öffnet den Repository-Dialog mit der URL schon ausgefüllt.

Ausführlich: [docs/installation.md](docs/installation.md).

## Dokumentation

- [Installation](docs/installation.md)
- [Backup und Restore](docs/backup.md)
- [Datenschutz](docs/datenschutz.md)
- [Häufige Fragen](docs/faq.md)
- [Entwicklung](docs/entwicklung.md)
- [Performance und Pi-4-Messung](docs/performance.md)
- [Sicherheitsrichtlinie](SECURITY.md)

## Entwicklung

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
ruff check .
ruff format --check .
yamllint -c .yamllint .
python scripts/validate_config.py
python scripts/bench.py

# oder alle Prüfungen gemeinsam:
PYTHON="$PWD/.venv/bin/python" scripts/check.sh
```

Die Datenbank liegt in Home Assistant unter `/data/finance.db`. Für lokale Entwicklung lässt sie sich mit `FINANCE_DB_PATH` überschreiben; `FINANCE_RESTRICT_INGRESS=0` deaktiviert die Proxy-IP-Sperre.

Die Oberfläche ist komplett servergerendert (Jinja2) und kommt ohne JavaScript und CDN aus. Interne Endpunkte (nur innerhalb des Add-ons):

- `/api/accounts`, `/api/categories`, `/api/transactions`, `/api/budgets` – `GET`/`POST` sowie `GET`/`PUT`/`DELETE` für einzelne Datensätze
- Lesend: `/api/stats/monthly`, `/api/stats/categories`, `/api/stats/budgets`, `/api/stats/balance`
- `/healthz` für den Supervisor-Watchdog

Lokales Starten ohne Home Assistant:

```bash
FINANCE_DB_PATH=/tmp/finance.db FINANCE_RESTRICT_INGRESS=0 \
  uvicorn main:app --app-dir addons/finance/app --reload --port 8099
```

Danach `http://localhost:8099/` und `http://localhost:8099/healthz` aufrufen.

## Freigabe für v1.0

Die finale Repository-URL ist `https://github.com/karst3nl/homeassistant-finance` und steht in `repository.yaml`, `config.yaml`, Badge und Add-on-README. Sie darf nach dem ersten Push nicht mehr geändert werden – aus ihr leitet der Supervisor die Add-on-ID ab. Die verbleibenden Treffer von `YOUR_GITHUB_USER` in `scripts/validate_config.py` und `.github/workflows/release.yaml` sind bewusste Schutzprüfungen für Forks.

Offen für die Veröffentlichung:

1. Repository `karst3nl/homeassistant-finance` anlegen und `main` pushen.
2. Pi-4-Smoketest laut [docs/performance.md](docs/performance.md).
3. Version in `config.yaml` und `pyproject.toml` auf `1.0.0` setzen und `CHANGELOG.md` ergänzen.
4. GitHub Release `v1.0.0` publizieren. `.github/workflows/release.yaml` baut und signiert die Images für `aarch64`/`amd64`, pusht `1.0.0` und `latest` nach GHCR und veröffentlicht das Manifest.
5. GHCR-Paket nach dem ersten Push explizit public setzen.

## Lizenz

GPL-3.0 – siehe [LICENSE](LICENSE).
