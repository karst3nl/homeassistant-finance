# Fixkosten und wiederkehrende Buchungen

Seit Version 0.10.0 verwaltet Finance wiederkehrende Posten in einer eigenen Seite **Fixkosten**. Aus jeder Regel erzeugt das Add-on automatisch ganz normale Buchungen – ohne externen Dienst, ohne Timer-Prozess und ohne Netzwerkzugriff. Gehalt gehört seit 0.13.0 nicht mehr hierher, sondern auf die Seite **Monatsgehalt** ([Anleitung](monatsgehalt.md)). Seit 0.14.0 kann eine Regel auch eine wiederkehrende **Umbuchung** zwischen zwei Konten sein.

## Beispiel

Miete 900 € monatlich und Versicherung 120 € jährlich:

1. **Konten** → Konto anlegen (falls noch nicht vorhanden).
2. Optional **Kategorien** → passende Ausgaben-/Einnahmekategorien anlegen.
3. **Fixkosten** → *Neue Regel* ausfüllen:
   - Name, Art (Ausgabe/Einnahme), Intervall (monatlich/jährlich), Betrag
   - Konto, optional Kategorie und Gegenstelle
   - erstes Fälligkeitsdatum
4. *Regel anlegen*. Die fälligen Buchungen erscheinen sofort unter **Buchungen** und fließen in Saldo, Budgets und Auswertungen ein.

Für das monatliche Gehalt bitte **Monatsgehalt** verwenden; dort wird der Auszahlungstag festgelegt und die Einnahme automatisch monatlich gebucht.

## Wiederkehrende Umbuchung

Seit 0.14.0 steht bei **Art** zusätzlich **Umbuchung** zur Verfügung. Damit legst du fest, dass ein Betrag regelmäßig von einem Konto auf ein anderes übertragen wird:

1. **Art** → *Umbuchung* wählen.
2. Unter **Konto / Quellkonto** das abgebende Konto und unter **Zielkonto** das empfangende Konto auswählen (zwei verschiedene Konten).
3. Betrag, Intervall und erstes Fälligkeitsdatum wie gewohnt angeben. Eine Kategorie wird bei Umbuchungen nicht benötigt.

**Wichtig:** Das Zielkonto wird nur bei **Art = Umbuchung** verwendet. Bis 0.15.0 wurde ein versehentlich bei Ausgabe/Einnahme gesetztes Zielkonto still ignoriert; seit 0.15.1 bricht das Formular mit einem Hinweis ab. Prüfe bei einer vorhandenen Regel in der Fixkostenliste, dass **Umbuchung** und `Quelle → Ziel` stehen.

Pro Fälligkeit entsteht ein ganz normales Umbuchungspaar: Eine negative Buchung auf dem Quellkonto und eine positive auf dem Zielkonto. Der Gesamtsaldo bleibt gleich; die Buchungen zählen nicht als Einnahme oder Ausgabe und erscheinen unter **Buchungen** mit „Umbuchung“. Details: [umbuchungen.md](umbuchungen.md).

Falls vor dem Update schon eine einfache Ausgabe gebucht wurde: Regel auf **Umbuchung** korrigieren, die falsche Ausgabe unter **Buchungen** löschen und den Betrag einmalig unter **Umbuchungen** anlegen. Bereits gebuchte Termine werden nicht automatisch umgewandelt.

## Wann wird gebucht?

- Beim **Start des Add-ons** und bei jedem Zugriff auf die Oberfläche (auch beim `/healthz`-Watchdog des Supervisors).
- Eine Regel bucht, sobald `next_due <= heute` ist; danach rückt das Datum um einen Monat bzw. ein Jahr weiter.
- Ein Datum in der **Vergangenheit** bucht alle seitdem fälligen Termine nach (aus Gründen der Sicherheit höchstens 120 pro Lauf und Regel).
- `recurring_rule_id` + `recurring_period` sind eindeutig: mehrfache Läufe erzeugen **keine Duplikate**, auch nicht nach einem Neustart oder einem Backup-Restore.

Monatsenden werden auf die tatsächliche Monatslänge begrenzt: Ein 31.01. wird im Februar zum 28./29.; die Folge rechnet ab diesem gekürzten Datum weiter.

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
