# Changelog

Alle nennenswerten Änderungen werden hier dokumentiert. Das Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/), die Versionierung an [Semantic Versioning](https://semver.org/lang/de/).

## [0.9.0] - 2026-11-20

Release-Kandidat für v1.0. Noch nicht veröffentlicht: finale Repository-URL, GHCR-Image und Pi-4-Messung stehen aus.

### Hinzugefügt

- Konsistenter SQLite-Snapshot über `backup_pre`/`backup_post` für Home-Assistant-Backups
- Option `log_level` mit de/en-Übersetzungen im Add-on-Store
- Security-Headers, 64-KB-Request-Limit, Obergrenze für Cent-Beträge und begrenzte Suchbegriffe
- Streng validierter `X-Ingress-Path` (kein Pfad mehr zu externen Hosts möglich)
- Release-Workflow mit den komponierbaren `home-assistant/builder`-Actions für `aarch64` und `amd64`, Signierung und GHCR-Manifest
- `pip-audit` in CI sowie `scripts/bench.py` für reproduzierbare Performance-Messungen
- Dokumentation zu Installation, Backup, Datenschutz, FAQ, Entwicklung und Performance

### Geändert

- Add-on verweist auf ein GHCR-Image statt lokalem Build; `run.sh` übernimmt den Uvicorn-Start
- Basisimage und Architektur in der Roadmap an das tatsächliche Dockerfile angepasst
- 62 automatisierte Tests, alle Checks grün

## [0.3.0] - 2026-11-19

### Hinzugefügt

- Auswertungsseite mit Monatsvergleich, Ausgaben nach Kategorie, Budget-Fortschritt und Saldo-Verlauf
- Serverseitig erzeugte SVG-Charts (Balken, Ring, Linie) ohne JavaScript und ohne CDN
- Budget-Verwaltung über die Oberfläche: anlegen, Limit ändern, löschen
- Budgets auf dem Dashboard für den aktuellen Monat
- Lesende Statistik-API unter `/api/stats/{monthly,categories,budgets,balance}`
- Perioden-Helfer für Monatsgrenzen, Schaltjahre und Monatsfolgen
- 13 neue Tests inklusive Gegenprobe der Kennzahlen gegen die Rohdaten

### Geändert

- Monatsausgaben auf dem Dashboard nutzen dieselbe Periodenlogik wie die Auswertungen

## [0.2.0] - 2026-11-19

### Hinzugefügt

- Dashboard mit Kontoständen, Gesamtsaldo und Monatsausgaben
- Formular zur Eingabe von Ausgaben und Einnahmen direkt auf dem Dashboard
- Seiten für Buchungen (mit Filter/Suche), Konten und Kategorien inkl. Löschen
- Servergerenderte Jinja2-Templates und schlankes CSS ohne JavaScript/CDN
- Berücksichtigung des Ingress-Pfads für Links, Redirects und Stylesheet

## [0.1.0] - 2026-11-19

### Hinzugefügt

- SQLite-Schema mit Konten, Kategorien, Buchungen, Budgets und Einstellungen (Migration 001)
- Cent-Arithmetik ohne Fließkommafehler, inklusive deutscher Betragsformate
- Interne CRUD-API für alle vier Entitäten mit Validierung, Filtern und 400/404/409-Fehlern
- Initialisierung der Datenbank beim Start über Lifespan, konfigurierbar via `FINANCE_DB_PATH`
- 30 automatische Tests für Arithmetik, API, Ingress-Sperre und Neustart-Persistenz

### Geändert

- Zeitstempel mit Millisekundenauflösung, damit Aktualisierungen erkennbar sind

## [0.0.1] - 2026-11-19

### Hinzugefügt

- Grundgerüst des Custom Repositories: `repository.yaml`, `config.yaml`, `Dockerfile`, Icons
- Hello-World-Ingress-Seite und `/healthz`-Endpunkt
- GPL-3.0-Lizenz, README und Roadmap
- CI-Skelett: Lint, Tests und Validierung der Add-on-Konfiguration
- Defense-in-Depth-Zugriffssperre auf den Supervisor-Proxy (`172.30.32.2`)
