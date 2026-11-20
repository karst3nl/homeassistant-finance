# Home Assistant Finance

[![Open your Home Assistant instance and show the add app repository dialog with a specific repository URL pre-filled.](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fkarst3nl%2Fhomeassistant-finance)

Ein schlankes, vollständig lokales Home-Assistant-Add-on für persönliche Finanzen. Kein Cloud-Konto, keine Bankverbindung, keine zusätzlichen Add-ons – nur ein Webserver-Prozess, eine SQLite-Datei und eine Oberfläche in Home Assistant.

> **Status:** Version **0.9.0** ist veröffentlicht und auf dem Raspberry Pi 4 getestet. **0.15.1** zeigt „Frei verfügbares Geld“ auf der Übersicht und verhindert, dass ein Zielkonto versehentlich als einfache Ausgabe gespeichert wird. Plan: [ROADMAP.md](ROADMAP.md).

## Umfang in v1

- Konten und Kategorien verwalten und bearbeiten
- Buchungen manuell erfassen, bearbeiten und löschen
- Monatliche und jährliche Fixkosten mit automatischer Buchung – inklusive wiederkehrender Umbuchungen zwischen Konten ([Anleitung](docs/fixkosten.md))
- Monatsgehalt als eigener Bereich mit automatischer Einnahmebuchung ([Anleitung](docs/monatsgehalt.md))
- Umbuchungen zwischen Konten als zusammenhängendes Buchungspaar ([Anleitung](docs/umbuchungen.md))
- Herunterladbare Backups und konsistente SQLite-Kopien ([Anleitung](docs/backup.md))
- Responsive, touchfreundliche Oberfläche für Desktop, Tablet und HA-Mobile-App
- Budgets pro Kategorie und Monat
- Übersicht mit frei verfügbarem Geld, Saldo, Monatsausgaben und SVG-Charts
- 100 % lokal, Ingress-UI ohne eigene Ports und ohne eigenes Login
- Keine HA-Entitäten, kein MQTT, kein Zugriff auf die HA-API

## Installation

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
- [Fixkosten und wiederkehrende Buchungen](docs/fixkosten.md)
- [Monatsgehalt](docs/monatsgehalt.md)
- [Umbuchungen zwischen Konten](docs/umbuchungen.md)
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

- `/api/accounts`, `/api/categories`, `/api/transactions`, `/api/transfers`, `/api/budgets`, `/api/recurring`, `/api/salary` – `GET`/`POST` sowie `GET`/`PUT`/`DELETE` für einzelne Datensätze
- Lesend: `/api/stats/monthly`, `/api/stats/categories`, `/api/stats/budgets`, `/api/stats/balance`
- `/healthz` für den Supervisor-Watchdog

Lokales Starten ohne Home Assistant:

```bash
FINANCE_DB_PATH=/tmp/finance.db FINANCE_RESTRICT_INGRESS=0 \
  uvicorn main:app --app-dir addons/finance/app --reload --port 8099
```

Danach `http://localhost:8099/` und `http://localhost:8099/healthz` aufrufen.

## Releases

Die Repository-URL `https://github.com/karst3nl/homeassistant-finance` steht in `repository.yaml`, `config.yaml`, Badge und Add-on-README und bleibt stabil – aus ihr leitet der Supervisor die Add-on-ID ab. Die verbleibenden Treffer von `YOUR_GITHUB_USER` in `scripts/validate_config.py` und `.github/workflows/release.yaml` sind bewusste Schutzprüfungen für Forks.

- `0.9.0`: erstes veröffentlichtes Image, vom Pi-4-Test bestätigt.
- `0.10.0`: Bearbeitung und Fixkosten.
- `0.10.1`: Aktiver Menüpunkt in der Navigation.
- `0.11.0`: Umbuchungen zwischen Konten.
- `0.12.0`: Menüpunkt **Backups** mit herunterladbaren SQLite-Kopien.
- `0.12.1`: Mobile/touchfreundliche Oberfläche für die Home-Assistant-App.
- `0.13.0`: Eigener Menüpunkt **Monatsgehalt** mit automatischer Einnahmebuchung.
- `0.14.0`: Fixkostenregeln können als **Umbuchung** zwischen zwei Konten angelegt werden.
- `0.15.0`: Die Übersicht zeigt oben **frei verfügbares Geld** als Planungswert.
- `0.15.1`: Ein Zielkonto ohne die Art **Umbuchung** wird abgelehnt statt ignoriert.

Ein Release publiziert `.github/workflows/release.yaml`: Es baut und signiert die Images für `aarch64`/`amd64`, pusht die Version und `latest` nach GHCR und veröffentlicht das Multi-Arch-Manifest. Das GHCR-Paket ist öffentlich. Das Image wird ausschließlich über das Custom Repository installiert; ein lokaler Build ist nicht nötig.

## Lizenz

GPL-3.0 – siehe [LICENSE](LICENSE).
