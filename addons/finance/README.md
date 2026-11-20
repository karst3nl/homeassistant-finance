# Finance

Ein vollständig lokales Add-on für persönliche Finanzen. Es läuft komplett auf deinem Home-Assistant-Gerät: keine Cloud, kein Konto, keine Bankverbindung und keine zusätzlichen Add-ons.

## Funktionsumfang

- Konten und Kategorien anlegen und bearbeiten
- Einnahmen und Ausgaben manuell erfassen, filtern, bearbeiten und löschen
- Monatliche und jährliche Fixkosten: Regeln pflegen und fällige Buchungen automatisch erzeugen
- Umbuchungen zwischen zwei Konten als zusammenhängendes Buchungspaar
- Herunterladbare Backups: aktuelle Datenbank direkt speichern oder Kopien verwalten
- Budgets pro Kategorie und Monat inklusive Fortschrittsanzeige
- Dashboard mit Saldo und Monatsausgaben
- Auswertungen mit Monatsvergleich, Kategorie-Anteilen und Saldo-Verlauf als SVG-Charts
- Bedienung rein über die Oberfläche – servergerendert, ohne JavaScript und ohne CDN
- Desktop-Layout bleibt erhalten; auf kleinen Touch-Displays passt sich Navigation und Tabellenansicht automatisch an

## Bedienung

Zuerst unter **Konten** ein Konto anlegen (optional unter **Kategorien** eine Ausgabekategorie). Danach kann auf der Übersicht eine Ausgabe oder Einnahme eingetragen werden. Buchungen und Konten lassen sich in der jeweiligen Liste über **Bearbeiten** ändern.

Wiederkehrende Posten wie Miete oder Versicherung werden unter **Fixkosten** als monatliche oder jährliche Regel angelegt. Das Add-on erzeugt die fälligen Buchungen automatisch; pausierte Regeln buchen nichts. Bereits erzeugte Buchungen bleiben erhalten, wenn eine Regel gelöscht wird.

Unter **Umbuchungen** verschiebst du Guthaben zwischen zwei Konten. Finance legt dafür zwei verknüpfte Buchungen an; der Gesamtsaldo bleibt gleich. Umbuchungen zählen nicht als Einnahme oder Ausgabe und beeinflussen keine Budgets.

Unter **Backups** lädst du die aktuelle Datenbank als SQLite-Datei herunter oder speicherst eine Kopie im Add-on, die du später erneut laden und löschen kannst. Die Dateien sind konsistent – auch während Buchungen geschrieben werden.

Nach dem Start erscheint **Finanzen** in der Seitenleiste. Ein Klick öffnet die Oberfläche innerhalb von Home Assistant. Ein separates Passwort gibt es nicht – die Anmeldung läuft über Home Assistant. Das Panel ist standardmäßig nur für Admins sichtbar.

## Daten und Backup

Alle Daten liegen in `/data/finance.db`. Vor einem Home-Assistant-Backup erzeugt das Add-on einen konsistenten Snapshot; danach wird er wieder entfernt. Eigene Backups liegen unter `/data/backups` und werden ebenfalls mitgesichert. Backups enthalten persönliche Finanzdaten – bitte entsprechend schützen.

## Konfiguration

Optional lässt sich die Protokollstufe (`log_level`) einstellen. Für den Normalbetrieb ist `info` richtig; `debug` nur für die Fehlersuche. Buchungsinhalte werden nie geloggt.

## Datenschutz

- Alle Daten bleiben auf dem Gerät (`/data`).
- Keine externen Netzwerkverbindungen zur Laufzeit.
- Keine Zugriffe auf die Home-Assistant- oder Supervisor-API.
- Keine Entitäten, Sensoren oder MQTT-Themen.
- Die Weboberfläche akzeptiert nur Anfragen des Supervisor-Proxys.

## Support

Fehler und Ideen: [GitHub Issues](https://github.com/karst3nl/homeassistant-finance/issues). Weitere Hinweise stehen in der [README](https://github.com/karst3nl/homeassistant-finance).
