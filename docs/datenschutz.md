# Datenschutz

Finance ist vollständig lokal. Es gibt keinen Cloud-Dienst, kein Benutzerkonto und keine Telemetrie.

## Was gespeichert wird

In `/data/finance.db` liegen nur die Daten, die du selbst eingibst:

- Konten und Startsaldi
- Kategorien
- Manuelle Buchungen mit Datum, Betrag, Gegenstelle und Beschreibung
- Budgets

Geldbeträge werden als ganzzahlige Cent gespeichert. Es werden keine Bankzugangsdaten, Kontonummern oder Belege erfasst.

## Was das Add-on nicht tut

- Keine externen HTTP-Aufrufe zur Laufzeit, auch keine Fonts oder CDN-Ressourcen
- Kein Zugriff auf die Home-Assistant- oder Supervisor-API
- Keine Sensoren, Entitäten oder Automatisierungsdaten
- Keine Ports nach außen: nur Ingress über den Supervisor
- Kein eigenes Login: die Anmeldung läuft über Home Assistant
- Keine Protokollierung von Buchungsinhalten (nur Metadaten und Fehler)

## Zugriffsschutz

Der Webserver akzeptiert Anfragen nur vom Supervisor-Proxy (`172.30.32.2`); für lokale Entwicklung lässt sich diese Prüfung mit `FINANCE_RESTRICT_INGRESS=0` deaktivieren. Zusätzlich setzt die Anwendung Security-Headers und begrenzt die Größe von Requests und Formularen.

Standardmäßig ist das Panel nur für Home-Assistant-Admins sichtbar (`panel_admin: true`).

## Backups

Home-Assistant-Backups enthalten die Finanzdaten im Klartext in der SQLite-Datei. Bitte entsprechend schützen. Details: [backup.md](backup.md).

## Lizenz

GPL-3.0. Der Quelltext ist öffentlich; es werden keine Nutzungsdaten erhoben.
