# Roadmap: Home-Assistant-Finance

**Stand:** 2026-11-20  
**Status:** Phase 0–5 abgeschlossen (0.9.0 veröffentlicht und auf dem Pi 4 getestet); Phase 6 ergänzt Umbuchungen (0.11.0), Phase 7 herunterladbare Backups (0.12.0), Phase 8 mobile/touchfreundliche Oberfläche (0.12.1), Phase 9 das Monatsgehalt als eigenen Bereich (0.13.0), Phase 10 wiederkehrende Umbuchungen in den Fixkosten (0.14.0), Phase 11 die Kennzahl „Frei verfügbares Geld“ (0.15.0), Patch 0.15.1 härtet die Zielkonto-Validierung ab, Patch 0.15.2 färbt die Monatsausgaben rot  
**Repo:** GitHub, Custom Repository für Home Assistant

---

## 1. Festgelegte Entscheidungen

| Punkt | Entscheidung | Konsequenz |
|---|---|---|
| Datenquellen in v1 | **Nur manuelle Erfassung** | Kein CSV-Parser, keine Bankverbindung, kein `importers/`-Modul in v1 |
| Lizenz | **GPL-3.0** | `LICENSE`-Datei im Repo-Root, Binärdistribution muss Quellangebot oder Link enthalten |
| Rückgabe an HA | **Keine – reine UI** | Kein `homeassistant_api`, keine Sensoren, kein MQTT, kein `services:` |
| Dokumentation | Diese Datei | Roadmap liegt im Repo-Root und wird mit jedem Release aktualisiert |
| Wiederkehrende Buchungen | **Eigene Fixkosten-Seite + automatische Buchungen** (ab 0.10.0) | Regeln werden manuell gepflegt, das Add-on erzeugt fällige Buchungen lokal; keine Bankabfrage |
| Umbuchungen | **Eigene Seite + verknüpftes Buchungspaar** (ab 0.11.0) | Zwei Buchungen mit `transfer_id`, Netto-Saldo 0; aus Einnahme/Ausgabe und Budgets ausgeschlossen |
| Monatsgehalt | **Eigene Seite + eigene Gehaltsregeln** (ab 0.13.0) | Monatliche Einnahme mit `source = 'salary'` und Idempotenz pro Monat; nicht unter Fixkosten |
| Wiederkehrende Umbuchung | **Fixkostenregel mit Zielkonto** (ab 0.14.0) | Erzeugt ein `transfers`-Paar; Herkunft und Zeitraum am Transfer, keine Einnahme/Ausgabe |
| Frei verfügbares Geld | **Kennzahl auf der Übersicht** (ab 0.15.0) | Gehalt − Fixkosten − geplante Umbuchungen; Planungswert ohne gebuchte Beträge |

> **Begriffsklärung:** „Reine UI" bedeutet: Es entstehen keine HA-Entitäten und keine Automatisierungsdaten. Die Oberfläche kommuniziert intern weiterhin über HTTP-Endpunkte mit dem Backend im selben Container – das ist Technik innerhalb des Add-ons, keine HA-Integration.

---

## 2. Zielbild und Rahmenbedingungen

Ein vollständig lokales, quelloffenes Add-on zur Verwaltung persönlicher Finanzen, das als Custom Repository auf GitHub liegt und auf HA OS / Raspberry Pi 4 flüssig läuft.

**Leitprinzip – „so schlank wie möglich":** *Ein Prozess, eine Sprache, eine SQLite-Datei, kein Node zur Laufzeit, keine HA-API, keine Cloud.*

| Rahmen | Festlegung |
|---|---|
| Zielhardware | HA OS 64-bit auf Raspberry Pi 4 → `arch: [aarch64, amd64]`; `armv7` ist deprecated und wird nicht gebaut |
| Betrieb | 100 % lokal, keine Telemetrie, keine externen HTTP-Calls zur Laufzeit |
| Datenhaltung | `/data` (Supervisor-mount), SQLite im WAL-Modus, Beträge als `INTEGER` Cent |
| UI | Ingress im HA-Sidebar, keine eigenen Ports, kein eigenes Login |
| Installation | Custom Repository + fertige Multi-Arch-Images aus GHCR |
| v1-Scope | Konten, Kategorien, Transaktionen (manuell), Budgets, Auswertungen |
| Bewusst später | CSV-Import, FinTS/HBCI, Belege, Sparziele, Sensoren, Multi-User |
| Nach v1 (0.10.0) | Bearbeitung von Konten/Buchungen, Fixkosten mit automatischer Buchung |
| Nach v1 (0.11.0) | Umbuchungen zwischen Konten als zusammenhängendes Paar |
| Nach v1 (0.12.0) | Herunterladbare Backups direkt aus der Oberfläche |
| Nach v1 (0.12.1) | Responsive, touchfreundliche Darstellung für die HA-Mobile-App |
| Nach v1 (0.13.0) | Monatsgehalt als eigener Menüpunkt, getrennt von den Fixkosten |
| Nach v1 (0.14.0) | Wiederkehrende Umbuchungen als Option einer Fixkostenregel |
| Nach v1 (0.15.0) | Planungswert „Frei verfügbares Geld“ oben auf der Übersicht |

**Ressourcenziele (auf dem Pi 4 messbar):** Image < 80 MB · RAM < 80 MB · Start < 5 s · CPU im Leerlauf ~0 %.

---

## 3. Architektur-Entscheidungen

| Bereich | Wahl | Warum |
|---|---|---|
| Base-Image | `ghcr.io/home-assistant/base-python:3.14-alpine3.24`, `init: false` | Offiziell, klein, klarer Update-Pfad; Python 3.14 ist im Image enthalten |
| Backend | Python 3.14 + **Starlette + Uvicorn** | Async, Routing, Static Files – ohne Pydantic-Overhead von FastAPI |
| Frontend | Jinja2-Templates + serverseitig erzeugte SVG-Charts, ohne JavaScript und ohne HTMX | Kein Build-Step, keine CDN-Abhängigkeit, ideal für Ingress und Pi 4 |
| Storage | Eine SQLite-Datei `/data/finance.db` | Zero-Admin, Backup = eine Datei, ideal für den Pi |
| Zugriff | `ingress: true`, `ingress_port: 8099`, Bind auf `0.0.0.0`, per Middleware nur `172.30.32.2` erlauben | Ingress kommt von der Container-IP, nicht von Loopback; keine Port-Freigabe, HA-Login wird genutzt |
| HA-Schnittstelle | Keine | `homeassistant_api` und `hassio_api` bleiben `false` (nur Basis-Selbstauskunft) |
| Netzwerk | `ports:` leer, `services:` leer | Keine zusätzlichen Add-ons nötig |
| Backup | `backup: hot` + `backup_pre` mit SQLite-`.backup()` | Konsistenter Snapshot während der Laufzeit |
| Sidebar | `panel_title: "Finanzen"`, `panel_icon: mdi:chart-pie`, `panel_admin: true` | Finanzdaten defaultmäßig nur für Admins |

**Kernidee:** Ein einzelner Webserver-Prozess liefert UI und interne API aus und schreibt in eine SQLite-Datei. Kein zweiter Dienst, keine Queue, kein DB-Server, keine Integration.

**Wichtige Ingress-Details:**
- Basis aus Header `X-Ingress-Path` (streng geprüft) für Links, Redirects und `<base>`; statische Dateien liegen unter `/static`.
- Kein `GET /addons/self/info` nötig – der Proxy liefert den Pfad im Header.
- `X-Remote-User-Id` wird in v1 nicht für Rechte verwendet; das Panel ist admin-only.
- `/healthz` als `watchdog` (`http://[HOST]:[PORT:8099]/healthz`).

---

## 4. Repository-Struktur (GitHub)

```text
repository.yaml                  # Custom-Repository-Metadaten
LICENSE                          # GPL-3.0
README.md                        # Mit "My Home Assistant"-Badge
ROADMAP.md                       # Diese Datei
CHANGELOG.md
addons/
  finance/
    config.yaml                  # <-- einzige Wahrheitsquelle für version
    Dockerfile
    icon.png, logo.png
    README.md                    # Add-on-Beschreibung im Store
    translations/{de,en}.yaml    # Options-Felder im HA-UI
    run.sh                       # Uvicorn-Start mit LOG_LEVEL aus den Optionen
    app/
      main.py                    # Uvicorn-Einstieg, IP-Sperre, Header, Limits
      backup.py                  # HA-Snapshot und herunterladbare SQLite-Kopien
      db.py                      # Verbindungen, PRAGMAs, Migrationen
      money.py, validation.py    # Cent-Arithmetik, Eingabeprüfung
      stats.py, reports.py       # Dashboard-Daten, Auswertungen
      charts.py                  # serverseitige SVG-Charts
      recurring.py               # Fixkosten-Regeln, Termine, Buchungserzeugung
      salary.py                  # Monatsgehalt: Gehaltsregeln und monatliche Einnahmen
      transfers.py               # Umbuchungen und verknüpfte Buchungen
      migrations/001_initial.sql, 002_recurring.sql, 003_transfers.sql, 004_salary.sql,
                 005_recurring_transfers.sql
      api/                       # accounts, categories, transactions, transfers, budgets, recurring, salary, stats
      templates/, static/        # Jinja2-Seiten und CSS ohne JS/CDN
docs/
  installation.md, backup.md (inkl. Download), datenschutz.md, faq.md, fixkosten.md, monatsgehalt.md, umbuchungen.md, entwicklung.md, performance.md
scripts/
  validate_config.py, bench.py   # Konfigurationscheck und Performance-Messung
tests/
.github/workflows/
  lint.yaml, test.yaml, build.yaml, security.yaml, release.yaml
```

⚠️ Der Supervisor findet `config.yaml` in beliebiger Tiefe – es darf im Repo **keine zweite** `config.yaml` geben.

---

## 5. Datenmodell (SQLite)

| Tabelle | Wichtige Felder |
|---|---|
| `accounts` | `id`, `name`, `type`, `currency`, `initial_balance_cents`, `active` |
| `categories` | `id`, `name`, `parent_id`, `type` (income/expense), `color`, `icon` |
| `transactions` | `id`, `account_id`, `booking_date`, `amount_cents`, `counterparty`, `description`, `category_id`, `source` (`manual`/`recurring`), `recurring_rule_id`, `recurring_period`, `created_at` |
| `budgets` | `id`, `category_id`, `period` (YYYY-MM), `limit_cents` |
| `recurring_rules` | `id`, `name`, `amount_cents`, `direction`, `interval` (monatlich/jährlich), `account_id`, `category_id`, `start_date`, `next_due`, `active` |
| `settings` | `key`, `value` |

- Alle Geldbeträge ganzzahlig in Cent → keine Rundungsfehler.
- Datumsfelder als `TEXT` im ISO-Format `YYYY-MM-DD` → sortierbar und SQLite-freundlich.
- Fremdschlüssel aktivieren (`PRAGMA foreign_keys = ON`), WAL-Modus (`PRAGMA journal_mode = WAL`).
- Migrationen als nummerierte SQL-Dateien, Version in `settings` oder `PRAGMA user_version`.
- `source` und `created_at` von Anfang an mitdenken, damit ein späterer CSV-Import ohne Schema-Bruch ergänzt werden kann.
- Migration 002 ergänzt Fixkosten-Regeln und die Herkunft automatischer Buchungen. Ein eindeutiger Index auf (`recurring_rule_id`, `recurring_period`) verhindert Doppelbuchungen.
- Migration 003 ergänzt `transfers` und `transactions.transfer_id`. Ein eindeutiger Index auf (`transfer_id`, `account_id`) verhindert halbe oder doppelte Umbuchungspaare.

---

## 6. Roadmap

Die Reihenfolge ist absichtlich: erst Datenkern, dann UI. Eine hübsche Oberfläche über einer unklaren Datenbank ist der häufigste Grund für spätere Rewrites.

**Fortschritt:** Phase 0 ✅ · Phase 1 ✅ · Phase 2 ✅ (UI bewusst ohne JavaScript/HTMX umgesetzt) · Phase 3 ✅ · Phase 4 ✅ (0.9.0 veröffentlicht, Pi-4-Test bestanden) · Phase 5 ✅ (0.10.1) · Phase 6 ✅ (Umbuchungen in 0.11.0) · Phase 7 ✅ (Backups-Download in 0.12.0) · Phase 8 ✅ (Mobile-Optimierung in 0.12.1).

| Phase | Inhalt | Meilenstein / Definition of Done | ca. Aufwand* |
|---|---|---|---|
| **0 – Fundament** | Repo anlegen, GPL-3.0, `repository.yaml`, `config.yaml`, Dockerfile, Hello-World-Ingress, CI-Skelett, README | Add-on ist im HA installierbar, Sidebar-Eintrag öffnet eine Seite | 1–2 d |
| **1 – Datenkern & API** | SQLite-Schema, Migrationen, CRUD-Endpunkte für Konten/Kategorien/Transaktionen/Budgets, Cent-Arithmetik, Tests | Alle Kernoperationen per API getestet, DB überlebt Neustart | 3–5 d |
| **2 – UI** | Dashboard, Buchungsliste mit Filter/Suche, Formular für manuelle Erfassung, Kategorien- und Budget-Pflege, Einstellungen, HA-Theme/Dark Mode | Komplette Bedienung rein über die Oberfläche möglich, kein curl nötig | 4–6 d |
| **3 – Auswertungen** | Monatsvergleich, Kategorie-Charts als SVG, Budget-Fortschritt, Saldo-Verlauf | Kennzahlen stimmen mit den Rohdaten überein (Gegenprobe per Test) | 2–3 d |
| **4 – Härtung & Veröffentlichung** | Security-Review ✅, Limits/Header/Snapshot ✅, de/en-Übersetzungen ✅, Docs ✅, Release-CI ✅, GHCR public ✅, Pi-4-Smoketest ✅ | 0.9.0 installierbar via Custom Repository | 2–4 d |
| **5 – Bearbeitung & Fixkosten** | Konten/Buchungen bearbeiten ✅, Fixkosten-Seite mit automatischer Buchung ✅, Migration 002 ✅, Doku ✅ | 0.10.1 veröffentlicht, Fixkosten auf dem Pi 4 geprüft | 1–2 d |
| **6 – Umbuchungen** | Umbuchungs-Seite ✅, zwei verknüpfte Buchungen ✅, Migration 003 ✅, Stats/Reports bereinigt ✅, Doku ✅ | 0.11.0 veröffentlicht, Umbuchungen auf dem Pi 4 geprüft | 1–2 d |
| **7 – Backups** | Menüpunkt **Backups** ✅, direkter SQLite-Download ✅, gespeicherte Kopien mit Download/Löschen ✅, strikte Dateinamensprüfung ✅, Doku ✅ | 0.12.0 veröffentlicht, Download auf dem Pi 4 geprüft | 1–2 d |
| **8 – Mobile-Optimierung** | Responsive Navigation ✅, Touch-Ziele ≥ 44 px ✅, Tabellen als beschriftete Karten ✅, Viewport/Safe-Area ✅, Doku ✅ | 0.12.1 veröffentlicht, in 390‑px‑Ansicht geprüft | 1 d |
| **9 – Optional (später)** | CSV-Import mit Mapping/Dedup, FinTS/HBCI, Belege, Sparziele, HA-Sensoren, Multi-User | Nur nach Feedback der ersten Nutzer | offen |

\* Grobe Schätzungen für eine Person, keine Zusage.

**Meilensteinübersicht:** M0 installierbar → M1 Daten stabil → M2 bedienbar → M3 auswertbar → M4 veröffentlicht.

---

## 7. UI-Skizze

```text
┌──────────────────────────────────────────────────────────┐
│ Finanzen  [Übersicht] [Buchungen] [Budgets] [Kategorien] [⚙] │
├──────────────────────────────────────────────────────────┤
│  Saldo gesamt        Ausgaben im November      [+ Buchung] │
│  12.480,50 €         1.243,80 €  ▼ 8 %                     │
│                                                          │
│  Budgets          ███████░░░ 72 % Lebensmittel            │
│                  ████░░░░░░ 40 % Mobilität               │
│                                                          │
│  Letzte Buchungen                                         │
│  18.11. REWE            -42,31 €   Lebensmittel   [✎][🗑] │
│  17.11. Gehalt        +2.850,00 €  Einkommen     [✎][🗑] │
└──────────────────────────────────────────────────────────┘
```

- Mobile zuerst, automatisch hell/dunkel über HA-CSS-Variablen.
- Neue Buchung: Datum, Konto, Betrag (Vorzeichen), Gegenstelle, Beschreibung, Kategorie.
- Filter nach Konto, Kategorie, Zeitraum, Suchbegriff; Listen sind sortierbar.
- Keine externen JS/CDN-Ressourcen – alles liegt im Image.

---

## 8. Sicherheit & Datenschutz

- Ingress-only: Bind auf `0.0.0.0:8099` (der Proxy kommt auf die Container-IP), per Middleware nur `172.30.32.2` akzeptieren, keine `ports`, kein `webui`.
- AppArmor aktiv, **keine** `privileged`-Capabilities, kein Host-Netzwerk, kein Docker-Socket, kein `auth_api`.
- Kein Zugriff auf Home Assistant oder Supervisor über die API – minimalste Berechtigungen.
- Logs enthalten nur Metadaten (z. B. „Buchung angelegt"), niemals Buchungsinhalte.
- Keine externen Netzwerkaufrufe zur Laufzeit (auch keine Font-/CDN-Links im UI).
- Dependency-Pinning, `pip-audit` in CI (`.github/workflows/security.yaml`), optional SBOM.
- Zusätzlich: Obergrenze für Cent-Beträge, 64-KB-Request-Limit, streng geprüfter `X-Ingress-Path`, Security-Headers und Längenbegrenzung der Suche.
- GPL-3.0: Quelltext öffentlich im Repo, Hinweis in der Add-on-README.

---

## 9. CI/CD & Release

1. **lint** – `yamllint`, `ruff`, `actionlint`, Pre-Commit.
2. **test** – `pytest` + Coverage; SQLite in `tmp_path`; TestClient für die Endpunkte; Tests für Cent-Arithmetik und Monatsgrenzen.
3. **build** – bei Änderung an `addons/finance/**` auf `main`: neue komponierbare Builder-Actions (`prepare-multi-arch-matrix` → `build-image` → `publish-multi-arch-manifest`) für `aarch64` + `amd64`, Push nach `ghcr.io/<user>/finance`. Permissions: `packages: write`, `id-token: write` für Cosign. **Image zuerst pushen, dann erst `version` in `config.yaml` erhöhen.** GHCR-Paket nach dem ersten Push explizit public setzen. (Das alte All-in-One-`home-assistant/builder`-Action ist deprecated.)
4. **release** – `.github/workflows/release.yaml` nutzt `version` und `image` aus `config.yaml` als einzige Quellen, baut/signiert `aarch64` + `amd64`, pusht `X.Y.Z` und `latest` nach GHCR und veröffentlicht das Manifest. Auslösung über GitHub Release `vX.Y.Z` oder manuell mit Versionsangabe. `breaking_versions` bei Migrationen setzen.
5. **Pi-4-Smoketest** (manuell vor jedem Minor-Release): Update über Custom Repository installieren, RAM/Startup messen, Ingress und Backup prüfen.

---

## 10. Teststrategie

- **Unit:** Cent-Arithmetik, Saldo- und Budgetberechnung, Datums-/Monatsgrenzen, Validierung der Formulareingaben.
- **Integration:** Alle CRUD-Endpunkte via Starlette-TestClient gegen temporäre SQLite-DB.
- **UI:** Smoke-Tests, dass Seiten rendern, Formulare wirken und der Ingress-Pfad in Links/Redirects ankommt.
- **Härtung:** Overflow-Schutz, Request-Limits, Security-Headers, Ingress-Pfad-Validierung, Backup-Snapshot.
- **Hardware:** Smoketest auf dem echten Raspberry Pi 4 bestanden (Install, Ingress, Backup); das Messprotokoll nach [docs/performance.md](docs/performance.md) ist weiterhin offen.

---

## 11. Dokumentation

Repo-README mit My-HA-Badge · Add-on-README im Store · `docs/installation.md` · `docs/backup.md` („eine Datei, restores über /data") · `docs/datenschutz.md` („es verlässt nichts den Pi") · `docs/faq.md` · `docs/fixkosten.md` · `docs/entwicklung.md` (lokal starten ohne HA) · `docs/performance.md` · CHANGELOG · de/en-Übersetzungen der Options-Felder. Alle Dateien sind angelegt.

---

## 12. Definition of Done für 0.9.0 / v1-Baseline

- [x] Add-on installierbar via Custom Repository, Image aus GHCR, kein lokaler Build nötig
- [x] Ingress-UI ohne eigene Ports und ohne eigenes Login
- [x] Konten, Kategorien, manuelle Buchungen und Budgets vollständig bedienbar
- [x] Auswertungen rechnerisch korrekt (Gegenprobe per Test)
- [x] Backup über `/data` funktioniert – Snapshot implementiert und getestet (ein HA-OS-Restore wurde nicht manuell geprüft)
- [x] Keine HA-API, keine Sensoren, keine externen Calls
- [x] Tests grün, Docs vollständig, GPL-3.0-Lizenz und CHANGELOG vorhanden
- [x] Auf einem Raspberry Pi 4 installiert und für gut befunden (Nutzerbestätigung; kein automatisiertes Messprotokoll)

---

## 13. Offene Punkte für später (bewusst nicht in v1)

- CSV-Import mit Spalten-Mapping und Deduplizierung – Datenmodell ist dafür schon vorbereitet (`source`, `created_at`).
- Bankabruf via FinTS/HBCI – nur mit expliziter Freigabe, nie mit Zugangsdaten in der App-DB.
- HA-Sensoren – falls doch gewünscht, über Supervisor-Proxy statt MQTT.
- Multi-User / Rechte über `X-Remote-User-Id` – aktuell sieht jeder Admin dieselben Daten.
- Belege, Sparziele, Export. Wiederkehrende Buchungen sind seit 0.10.0 umgesetzt (siehe [docs/fixkosten.md](docs/fixkosten.md)), Umbuchungen seit 0.11.0 (siehe [docs/umbuchungen.md](docs/umbuchungen.md)).
