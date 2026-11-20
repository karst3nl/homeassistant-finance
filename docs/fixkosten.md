# Fixkosten und wiederkehrende Buchungen

Seit Version 0.10.0 verwaltet Finance wiederkehrende Posten in einer eigenen Seite **Fixkosten**. Aus jeder Regel erzeugt das Add-on automatisch ganz normale Buchungen – ohne externen Dienst, ohne Timer-Prozess und ohne Netzwerkzugriff.

## Beispiel

Miete 900 € monatlich, Versicherung 120 € jährlich, Gehalt 2.500 € monatlich:

1. **Konten** → Konto anlegen (falls noch nicht vorhanden).
2. Optional **Kategorien** → passende Ausgaben-/Einnahmekategorien anlegen.
3. **Fixkosten** → *Neue Regel* ausfüllen:
   - Name, Art (Ausgabe/Einnahme), Intervall (monatlich/jährlich), Betrag
   - Konto, optional Kategorie und Gegenstelle
   - erstes Fälligkeitsdatum
4. *Regel anlegen*. Die fälligen Buchungen erscheinen sofort unter **Buchungen** und fließen in Saldo, Budgets und Auswertungen ein.

## Wann wird gebucht?

- Beim **Start des Add-ons** und bei jedem Zugriff auf die Oberfläche (auch beim `/healthz`-Watchdog des Supervisors).
- Eine Regel bucht, sobald `next_due <= heute` ist; danach rückt das Datum um einen Monat bzw. ein Jahr weiter.
- Ein Datum in der **Vergangenheit** bucht alle seitdem fälligen Termine nach (aus Gründen der Sicherheit höchstens 120 pro Lauf und Regel).
- `recurring_rule_id` + `recurring_period` sind eindeutig: mehrfache Läufe erzeugen **keine Duplikate**, auch nicht nach einem Neustart oder einem Backup-Restore.

Monatsenden werden auf die tatsächliche Monatslänge begrenzt: der 31.01. wird im Februar zum 28./29., im März wieder zum 31.

## Regeln bearbeiten und pausieren

Über **Bearbeiten** lassen sich alle Felder ändern. Wichtig:

- Bereits erzeugte Buchungen bleiben unverändert – auch wenn sich Betrag oder Intervall ändern.
- Ändert sich das **erste Fälligkeitsdatum**, wird die Terminfolge ab diesem Datum neu berechnet. Schon gebuchte Termine werden nicht doppelt angelegt.
- Das Häkchen **Aktiv** pausiert eine Regel. Pausierte Regeln erzeugen keine Buchungen und rücken ihre Fälligkeit trotzdem weiter, damit ein Reaktivieren nicht nachträglich monatelange Buchungen anlegt.
- **Löschen** entfernt nur die Regel. Die bereits erzeugten Buchungen bleiben als normale Buchungen erhalten und lassen sich einzeln bearbeiten oder löschen.

Die Oberseite der Seite zeigt die geplanten Beträge pro Monat. Bei jährlichen Regeln wird der Betrag für diese Planung durch 12 geteilt (kaufmännisch gerundet); die tatsächliche Buchung erfolgt selbstverständlich in voller Höhe im Fälligkeitsmonat.

## Abgrenzung

- Fixkosten sind **keine HA-Entitäten** und keine Automatisierungen in Home Assistant.
- Es gibt keine Bankabfrage: Beträge und Termine werden manuell gepflegt.
- Eine gelöschte oder geänderte Buchung in der Vergangenheit wird nicht automatisch wiederhergestellt.
- Die interne API unter `/api/recurring` dient nur der Oberfläche im selben Container und ist nicht von außen erreichbar.
