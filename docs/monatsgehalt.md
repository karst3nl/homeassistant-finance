# Monatsgehalt

Seit Version 0.13.0 hat das Gehalt einen eigenen Menüpunkt **Monatsgehalt**. Es ist bewusst nicht mehr Teil der **Fixkosten**: dort stehen nur Ausgaben und wiederkehrende Einnahmen, die keine Gehälter sind.

## Gehalt einrichten

1. **Konten** → Konto anlegen, auf dem das Gehalt eingeht (falls noch nicht vorhanden).
2. Optional **Kategorien** → Einnahme-Kategorie wie „Gehalt“ anlegen.
3. **Monatsgehalt** → *Monatsgehalt einrichten* ausfüllen:
   - Name, Betrag und Konto
   - Datum der ersten Auszahlung (der Tag gilt als monatlicher Auszahlungstag)
   - optional Einnahme-Kategorie und Arbeitgeber als Gegenstelle
   - *Aktiv* – nur aktive Regeln buchen automatisch
4. *Gehalt anlegen*. Die Regel steht danach in der Tabelle; fällige Buchungen erscheinen sofort unter **Buchungen**.

Es können mehrere Regeln angelegt werden, zum Beispiel das Hauptsalary und eine zweite monatliche Einnahme. Die Summe aktiver Regeln steht oben als „Gehalt pro Monat“.

## Automatische Buchungen

- Beim Start des Add-ons und bei jedem Zugriff auf die Oberfläche – auch beim `/healthz`-Watchdog des Supervisors – prüft Finance alle Gehaltsregeln.
- Eine aktive Regel bucht eine positive Einnahme am monatlichen Auszahlungstag, sobald das Datum fällig ist.
- Fällt der Auszahlungstag in einem Monat auf einen nicht vorhandenen Tag (z. B. 31. Februar), wird er auf den letzten Tag des Monats begrenzt.
- Pro Regel und Monat entsteht höchstens eine Buchung (`salary_rule_id` + `salary_period`). Ein erneuter Start oder ein erneuter Seitenaufruf erzeugt keine Duplikate.
- Pausierte Regeln rücken ihren Termin ebenfalls weiter, buchen aber nichts. Nach dem Reaktivieren wird ab dem nächsten Termin gebucht, nicht rückwirkend.
- Gehaltsbuchungen tragen die Quelle `salary` und erscheinen in **Buchungen** mit dem Hinweis „Monatsgehalt“. Sie zählen zu Saldo, Einnahmen und Kategorie-Auswertungen, nicht aber zu Budgets (diese betreffen nur Ausgaben).

## Bearbeiten und löschen

Über **Bearbeiten** lassen sich Betrag, Konto, Kategorie, Datum und Status ändern. Bereits erzeugte Buchungen bleiben davon unberührt. Wird das Datum der ersten Auszahlung geändert, berechnet Finance die Folgetermine ab diesem Datum neu und bucht fehlende Monate nach.

Beim **Löschen** einer Regel bleiben bereits erzeugte Buchungen erhalten; nur die automatische Fortsetzung entfällt.
