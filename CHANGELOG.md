# Changelog

Alle nennenswerten Änderungen werden hier dokumentiert. Das Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/), die Versionierung an [Semantic Versioning](https://semver.org/lang/de/).

## [0.12.1] - 2026-11-20

### Hinzugefügt

- Responsive Anpassung für die Home-Assistant-Mobile-App: Touch-Ziele mindestens 44 px, horizontal scrollbare Navigation und Tabellen als beschriftete Karten auf schmalen Displays
- Viewport berücksichtigt Safe-Area-Insets; Formulare, Buttons und Charts skalieren auf kleine Bildschirme
- Navigation bleibt in der Breite und scrollt intern – kein horizontaler Seitenüberlauf auf dem Handy

## [0.12.0] - 2026-11-20

### Hinzugefügt

- Neuer Menüpunkt **Backups** mit Download der aktuellen Datenbank als konsistente SQLite-Datei
- Backups im Add-on speichern, auflisten, erneut herunterladen und löschen (`/data/backups`)
- Backups werden über `sqlite3.Connection.backup()` erzeugt – konsistent trotz WAL-Modus und laufender Buchungen
- Streng geprüfte Dateinamen für Downloads, sodass nur selbst erzeugte Backup-Dateien zugänglich sind

### Geändert

- `backup.py` teilt sich die Kopierlogik zwischen HA-Snapshot und herunterladbaren Backups
- Doku zu Backup/Restore, FAQ, Add-on-README und Development-Übersicht aktualisiert

## [0.11.0] - 2026-11-20

### Hinzugefügt

- Eigene Seite **Umbuchungen** zum Verschieben von Guthaben zwischen zwei Konten
- Umbuchung besteht aus zwei verknüpften Buchungen (Ausgabe im Quellkonto, Einnahme im Zielkonto) mit konsistenten Kontoständen
- Bearbeiten und Löschen einer Umbuchung aktualisiert/entfernt beide Buchungen gemeinsam
- Umbuchungen werden aus Einnahme/Ausgabe, Budgets und Kategorie-Auswertungen ausgeschlossen, bleiben aber in Kontoständen und Saldo-Verlauf sichtbar
- Migration 003, eigene API `/api/transfers` und 8 neue Tests

### Geändert

- Buchungen mit Herkunft `transfer` sind in der Buchungsliste gekennzeichnet und zeigen statt der Einzelbearbeitung einen Link zur Umbuchung
- Konten mit Umbuchungen lassen sich nicht löschen; Hinweise in FAQ und Add-on-README ergänzt

## [0.10.1] - 2026-11-20

### Hinzugefügt

- Aktiver Menüpunkt in der Navigation: Die aktuelle Seite ist farblich, fett und unterstrichen markiert und zusätzlich per `aria-current="page"` für Screenreader erkennbar
- Die Markierung bleibt auf Bearbeitungsseiten und hinter Home-Assistant-Ingress-Pfaden erhalten

## [0.10.0] - 2026-11-20

### Hinzugefügt

- Konten und Buchungen lassen sich über die Oberfläche bearbeiten (Inklusive Aktiverkennung, Kategorien und Vorzeichen)
- Eigene Seite **Fixkosten** für monatliche und jährliche Regeln mit Name, Betrag, Konto, Kategorie und Fälligkeitsdatum
- Automatische Erzeugung fälliger Buchungen beim Start und beim Zugriff, inklusive Nachbuchung und Schutz vor Duplikaten
- Anzeige der geplanten Einnahmen/Ausgaben pro Monat (Jahresbeträge mit `/12`)
- Pausieren von Regeln, Bearbeiten mit Neuberechnung der Terminfolge und Löschen ohne Verlust bereits erzeugter Buchungen
- Migration 002 für bestehende Datenbanken, 13 neue Tests für Fixkosten und Bearbeitung

### Geändert

- Buchungsformular teilt sich zwischen Dashboard und Bearbeitungsseite und bietet Einnahme- und Ausgabekategorien
- `docs/fixkosten.md` als zusätzliche Anleitung; Hinweise in README, FAQ und Add-on-README

## [0.9.0] - 2026-11-20

Erste veröffentlichte Version. Repository-URL und GHCR-Image stehen; die Installation wurde auf dem Raspberry Pi 4 bestätigt.

### Hinzugefügt

- Konsistenter SQLite-Snapshot über `backup_pre`/`backup_post` für Home-Assistant-Backups
- Option `log_level` mit de/en-Übersetzungen im Add-on-Store
- Security-Headers, 64-KB-Request-Limit, Obergrenze für Cent-Beträge und begrenzte Suchbegriffe
- Streng validierter `X-Ingress-Path` (kein Pfad mehr zu externen Hosts möglich)
- Release-Workflow mit den komponierbaren `home-assistant/builder`-Actions für `aarch64` und `amd64`, Signierung und GHCR-Manifest
- `pip-audit` in CI sowie `scripts/bench.py` für reproduzierbare Performance-Messungen
- Dependabot für pip und GitHub Actions, `scripts/check.sh` als Sammelprüfung, `SECURITY.md` sowie Issue-/PR-Vorlagen
- Konsistenztests für Version, Image, Repository-URL, Badge, Übersetzungen und Dockerfile
- Dokumentation zu Installation, Backup, Datenschutz, FAQ, Entwicklung und Performance

### Geändert

- Add-on verweist auf ein GHCR-Image statt lokalem Build; `run.sh` übernimmt den Uvicorn-Start
- Basisimage und Architektur in der Roadmap an das tatsächliche Dockerfile angepasst
- 68 automatisierte Tests, alle Checks grün

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
