# Roadmap: Home-Assistant-Finance

**Stand:** 2026-11-20  
**Status:** Phase 0–3 abgeschlossen, Phase 4 in Umsetzung (Release-Kandidat 0.9.0)  
**Repo:** GitHub, Custom Repository für Home Assistant

---

## 1. Festgelegte Entscheidungen

| Punkt | Entscheidung | Konsequenz |
|---|---|---|
| Datenquellen in v1 | **Nur manuelle Erfassung** | Kein CSV-Parser, keine Bankverbindung, kein `importers/`-Modul in v1 |
| Lizenz | **GPL-3.0** | `LICENSE`-Datei im Repo-Root, Binärdistribution muss Quellangebot oder Link enthalten |
| Rückgabe an HA | **Keine – reine UI** | Kein `homeassistant_api`, keine Sensoren, kein MQTT, kein `services:` |
| Dokumentation | Diese Datei | Roadmap liegt im Repo-Root und wird mit jedem Release aktualisiert |

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
| Bewusst später | CSV-Import, FinTS/HBCI, Belege, Sparziele, wiederkehrende Buchungen, Sensoren, Multi-User |

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
      backup.py                  # Konsistenter SQLite-Snapshot für HA-Backups
      db.py                      # Verbindungen, PRAGMAs, Migrationen
      money.py, validation.py    # Cent-Arithmetik, Eingabeprüfung
      stats.py, reports.py       # Dashboard-Daten, Auswertungen
      charts.py                  # serverseitige SVG-Charts
      migrations/001_initial.sql
      api/                       # accounts, categories, transactions, budgets, stats
      templates/, static/        # Jinja2-Seiten und CSS ohne JS/CDN
docs/
  installation.md, backup.md, datenschutz.md, faq.md, entwicklung.md, performance.md
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
| `transactions` | `id`, `account_id`, `booking_date`, `amount_cents`, `counterparty`, `description`, `category_id`, `source` (v1 immer `manual`), `created_at` |
| `budgets` | `id`, `category_id`, `period` (YYYY-MM), `limit_cents` |
| `settings` | `key`, `value` |

- Alle Geldbeträge ganzzahlig in Cent → keine Rundungsfehler.
- Datumsfelder als `TEXT` im ISO-Format `YYYY-MM-DD` → sortierbar und SQLite-freundlich.
- Fremdschlüssel aktivieren (`PRAGMA foreign_keys = ON`), WAL-Modus (`PRAGMA journal_mode = WAL`).
- Migrationen als nummerierte SQL-Dateien, Version in `settings` oder `PRAGMA user_version`.
- `source` und `created_at` von Anfang an mitdenken, damit ein späterer CSV-Import ohne Schema-Bruch ergänzt werden kann.

---

## 6. Roadmap

Die Reihenfolge ist absichtlich: erst Datenkern, dann UI. Eine hübsche Oberfläche über einer unklaren Datenbank ist der häufigste Grund für spätere Rewrites.

**Fortschritt:** Phase 0 ✅ · Phase 1 ✅ · Phase 2 ✅ (UI bewusst ohne JavaScript/HTMX umgesetzt) · Phase 3 ✅ · Phase 4 🔄 (Härtung und Docs fertig, Veröffentlichung offen).

| Phase | Inhalt | Meilenstein / Definition of Done | ca. Aufwand* |
|---|---|---|---|
| **0 – Fundament** | Repo anlegen, GPL-3.0, `repository.yaml`, `config.yaml`, Dockerfile, Hello-World-Ingress, CI-Skelett, README | Add-on ist im HA installierbar, Sidebar-Eintrag öffnet eine Seite | 1–2 d |
| **1 – Datenkern & API** | SQLite-Schema, Migrationen, CRUD-Endpunkte für Konten/Kategorien/Transaktionen/Budgets, Cent-Arithmetik, Tests | Alle Kernoperationen per API getestet, DB überlebt Neustart | 3–5 d |
| **2 – UI** | Dashboard, Buchungsliste mit Filter/Suche, Formular für manuelle Erfassung, Kategorien- und Budget-Pflege, Einstellungen, HA-Theme/Dark Mode | Komplette Bedienung rein über die Oberfläche möglich, kein curl nötig | 4–6 d |
| **3 – Auswertungen** | Monatsvergleich, Kategorie-Charts als SVG, Budget-Fortschritt, Saldo-Verlauf | Kennzahlen stimmen mit den Rohdaten überein (Gegenprobe per Test) | 2–3 d |
| **4 – Härtung & v1.0** | Security-Review ✅, Limits/Header/Snapshot ✅, de/en-Übersetzungen ✅, Docs ✅, Release-CI ✅; Performance-Messung auf echtem Pi 4 und Veröffentlichung offen | v1.0.0 getaggt, Image public, Anleitung „in 3 Klicks installiert" | 2–4 d |
| **5 – Optional (später)** | CSV-Import mit Mapping/Dedup, FinTS/HBCI, Belege, Sparziele, wiederkehrende Buchungen, HA-Sensoren, Multi-User | Nur nach Feedback der ersten Nutzer | offen |

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
- **Hardware:** Messprotokoll auf dem echten Raspberry Pi 4 (Imagegröße, RAM, Startzeit, Ingress-Response), siehe [docs/performance.md](docs/performance.md). Noch offen.

---

## 11. Dokumentation

Repo-README mit My-HA-Badge · Add-on-README im Store · `docs/installation.md` · `docs/backup.md` („eine Datei, restores über /data") · `docs/datenschutz.md` („es verlässt nichts den Pi") · `docs/faq.md` · `docs/entwicklung.md` (lokal starten ohne HA) · `docs/performance.md` · CHANGELOG · de/en-Übersetzungen der Options-Felder. Alle Dateien sind angelegt.

---

## 12. Definition of Done für v1.0

- [ ] Add-on installierbar via Custom Repository, Image aus GHCR, kein lokaler Build nötig – **offen:** erster Push, GHCR-Paket public (URL ist auf `karst3nl/homeassistant-finance` festgelegt)
- [x] Ingress-UI ohne eigene Ports und ohne eigenes Login
- [x] Konten, Kategorien, manuelle Buchungen und Budgets vollständig bedienbar
- [x] Auswertungen rechnerisch korrekt (Gegenprobe per Test)
- [ ] Backup/Restore über `/data` funktioniert – Snapshot implementiert und getestet, HA-OS-Restore noch nicht manuell geprüft
- [x] Keine HA-API, keine Sensoren, keine externen Calls
- [x] Tests grün, Docs vollständig, GPL-3.0-Lizenz und CHANGELOG vorhanden
- [ ] Auf einem Raspberry Pi 4 gemessen und für gut befunden – **offen:** manuelles Messprotokoll

---

## 13. Offene Punkte für später (bewusst nicht in v1)

- CSV-Import mit Spalten-Mapping und Deduplizierung – Datenmodell ist dafür schon vorbereitet (`source`, `created_at`).
- Bankabruf via FinTS/HBCI – nur mit expliziter Freigabe, nie mit Zugangsdaten in der App-DB.
- HA-Sensoren – falls doch gewünscht, über Supervisor-Proxy statt MQTT.
- Multi-User / Rechte über `X-Remote-User-Id` – aktuell sieht jeder Admin dieselben Daten.
- Wiederkehrende Buchungen, Belege, Sparziele, Export.
