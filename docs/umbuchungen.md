# Umbuchungen zwischen Konten

Seit Version 0.11.0 können Guthaben zwischen zwei angelegten Konten verschoben werden. Die Funktion liegt im Menü **Umbuchungen** und benötigt mindestens zwei Konten.

## Anwendung

1. **Umbuchungen** öffnen.
2. Datum, Quellkonto (**Von**), Zielkonto (**Nach**), Betrag und optional eine Beschreibung eingeben.
3. **Umbuchung anlegen** klicken.

Beispiel: 250 € vom Girokonto auf das Sparkonto buchen. Danach sinkt der Giro-Saldo um 250 € und der Spar-Saldo steigt um 250 €. Der Gesamtsaldo bleibt unverändert.

## Was passiert intern?

Für jede Umbuchung legt Finance genau zwei Buchungen an:

- eine negative Buchung auf dem Quellkonto (`counterparty`: „nach <Zielkonto>“)
- eine positive Buchung auf dem Zielkonto (`counterparty`: „von <Quellkonto>“)

Beide Buchungen tragen die Herkunft `transfer` und sind über eine `transfer_id` miteinander verknüpft. Die beiden Buchungen erscheinen unter **Buchungen** mit dem Hinweis „Umbuchung“.

## Auswirkungen auf Auswertungen

Umbuchungen sind **keine Einnahmen und keine Ausgaben**. Sie werden deshalb bewusst aus folgenden Auswertungen ausgeschlossen:

- Ausgaben diesen Monat auf der Übersicht
- Monatsvergleich und Netto-Betrachtung
- Kategorie-Anteile
- Budget-Fortschritt

Die Kontostände und der Saldo-Verlauf enthalten die Umbuchungen selbstverständlich – sonst stimmten die Kontostände nicht mehr.

## Bearbeiten und Löschen

Über **Bearbeiten** lassen sich Datum, Konten, Betrag und Beschreibung ändern. Beide Buchungen werden dabei gemeinsam aktualisiert. **Löschen** entfernt die Umbuchung und beide zugehörigen Buchungen.

Die einzelnen Buchungen einer Umbuchung können nicht separat bearbeitet oder gelöscht werden; die Oberfläche verlinkt stattdessen direkt auf die Umbuchung. Ein Konto kann nicht gelöscht werden, solange es an einer Umbuchung beteiligt ist.

## Wiederkehrende Umbuchungen

Seit 0.14.0 können Umbuchungen auch als Regel unter **Fixkosten** angelegt werden: **Art = Umbuchung**, Quellkonto, Zielkonto, Betrag und Intervall festlegen. Das Add-on erzeugt dann zu jedem Termin automatisch dasselbe Buchungspaar wie eine manuell angelegte Umbuchung. Pro Regel und Monat (bzw. Jahr) entsteht höchstens eine Umbuchung; pausierte Regeln buchen nichts. Bereits erzeugte Umbuchungen bleiben erhalten, wenn die Regel gelöscht wird. Details: [fixkosten.md](fixkosten.md#wiederkehrende-umbuchung).

Die interne API unter `/api/transfers` ist wie die übrigen `/api/...`-Endpunkte nur innerhalb des Add-ons erreichbar.
