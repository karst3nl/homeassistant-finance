# Installation

## Voraussetzungen

- Home Assistant OS 64-bit (Raspberry Pi 4 oder x86-64)
- Supervisor und Apps/Add-ons aktiviert
- Ein Admin-Konto in Home Assistant

Es werden keine weiteren Add-ons, kein MQTT und kein Cloud-Konto benötigt.

## Custom Repository hinzufügen

1. In Home Assistant: **Einstellungen → Apps → App installieren → Repositories**
2. **Repository hinzufügen** wählen und eintragen:

   ```text
   https://github.com/karst3nl/homeassistant-finance
   ```

3. Add-on **Finance** aus der Liste installieren.
4. Add-on starten. Beim ersten Start wird `/data/finance.db` angelegt und migriert.
5. In der Seitenleiste auf **Finanzen** klicken.

Der My-Home-Assistant-Badge in der [README](../README.md) öffnet den Dialog mit der Repository-URL schon ausgefüllt.

## Erste Schritte

1. In der Oberfläche unter **Konten** ein Konto anlegen (z. B. Girokonto mit Startsaldo).
2. Optional unter **Kategorien** Kategorien wie „Lebensmittel" oder „Gehalt" anlegen.
3. Auf der **Übersicht** die erste Ausgabe oder Einnahme erfassen.
4. Unter **Budgets** für den aktuellen Monat ein Limit setzen.

## Updates

Das Image liegt in GHCR. Bei einer neuen Version erscheint im Add-on die Schaltfläche **Aktualisieren**. Der Supervisor lädt das passende Image für `aarch64` oder `amd64`; ein lokaler Build ist nicht nötig.

## Deinstallation

Beim Entfernen des Add-ons bleibt `/data` zunächst erhalten. Die Datenbank lässt sich vorher über ein Home-Assistant-Backup sichern (siehe [backup.md](backup.md)).

## Entwicklungsinstallation

Ohne Home Assistant kann die Oberfläche direkt gestartet werden:

```bash
pip install -r requirements-dev.txt
FINANCE_DB_PATH=/tmp/finance.db FINANCE_RESTRICT_INGRESS=0 \
  uvicorn main:app --app-dir addons/finance/app --reload --port 8099
```

Danach `http://localhost:8099/` öffnen.
