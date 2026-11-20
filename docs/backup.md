# Backup und Restore

Alle Daten liegen in einer einzigen SQLite-Datei: `/data/finance.db`. Home Assistant sichert das Verzeichnis `/data` dieses Add-ons bei einem vollständigen Backup mit.

## Warum ein Snapshot nötig ist

SQLite nutzt den WAL-Modus. Beim Kopieren der Datenbank während des laufenden Betriebs könnten Änderungen in `-wal`/`-shm`-Dateien fehlen. Deshalb erzeugt das Add-on vor jedem Backup über `backup_pre` einen konsistenten Snapshot:

```text
python3 /app/backup.py pre   → /data/finance.db.snapshot
python3 /app/backup.py post  → entfernt den Snapshot wieder
```

`sqlite3.Connection.backup()` liest dabei einen transaktional konsistenten Zustand – auch wenn gerade Buchungen geschrieben werden. Der Snapshot ist eine normale SQLite-Datei und wird vom Supervisor mitgesichert.

## Backup erstellen

In Home Assistant: **Einstellungen → System → Backups → Backup erstellen**. Das Add-on muss dazu nicht gestoppt werden (`backup: hot`).

## Backup im Add-on herunterladen

Seit Version 0.12.0 gibt es im Add-on den Menüpunkt **Backups**:

- **Aktuelle Datenbank herunterladen** erzeugt sofort eine konsistente SQLite-Kopie und startet den Download. Es wird keine Datei im Add-on abgelegt.
- **Backup speichern** legt eine Kopie unter `/data/backups` ab. Dort kann sie in der Liste erneut heruntergeladen oder gelöscht werden.

Beide Wege nutzen `sqlite3.Connection.backup()` und funktionieren deshalb auch bei laufendem Betrieb und WAL-Modus. Die Dateien heißen zum Beispiel `finance-20261120-154500-a1b2c3d4.db`; nur solche vom Add-on erzeugten Namen werden zum Download freigegeben.

Gespeicherte Backups liegen im `/data`-Verzeichnis des Add-ons und sind damit auch Teil der Home-Assistant-Backups. Sie werden nicht automatisch gelöscht – bei Bedarf die Liste unter **Backups** aufräumen.

## Restore

1. Backup in Home Assistant wiederherstellen.
2. Add-on starten.
3. Falls nur die Datenbank manuell zurückgespielt wurde: `/data/finance.db.snapshot` oder eine heruntergeladene Backup-Datei nach `/data/finance.db` kopieren und das Add-on neu starten.

Nach dem Start prüft das Add-on `PRAGMA user_version` und wendet fehlende Migrationen automatisch an. Ein Downgrade auf eine ältere Version ist nicht vorgesehen.

## Prüfen, ob alles da ist

```bash
# Im Container / auf dem Gerät mit sqlite3
sqlite3 /data/finance.db "SELECT COUNT(*) FROM transactions;"
```

Alternativ: Die Oberfläche zeigt unter **Buchungen** alle Einträge und unter **Auswertungen** die Kennzahlen.

## Hinweise

- Die Snapshot-Datei ist nur während des Backup-Vorgangs vorhanden.
- Backups enthalten persönliche Finanzdaten: getrennt aufbewahren und nicht öffentlich teilen.
- Bei sehr großen Datenbanken (viel mehr als die im Projekt erwarteten Mengen) kann der Snapshot kurz dauern; das Add-on bleibt währenddessen erreichbar.
