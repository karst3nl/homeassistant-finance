# Häufige Fragen

## Warum sehe ich keine Sensoren oder Entitäten in Home Assistant?

Das Add-on ist bewusst eine „reine UI": Es gibt keine HA-Entitäten, keine MQTT-Themen und keine Automatisierungen. Die Daten bleiben in der SQLite-Datei des Add-ons und werden nur in dessen Ingress-Oberfläche angezeigt.

## Werden meine Bankkonten automatisch abgefragt?

Nein. Es gibt keine Bankverbindung, kein FinTS/HBCI und keinen CSV-Import. Wiederkehrende Buchungen werden ausschließlich aus selbst angelegten Regeln unter **Fixkosten** erzeugt – also lokal und manuell gepflegt.

## Ist die Oberfläche für die Home-Assistant-Mobile-App geeignet?

Ja. Ab 0.12.1 passt sich das Layout an die Bildschirmbreite an: Die Navigation ist horizontal scrollbar, Buttons und Eingabefelder sind mindestens 44 px hoch und Tabellen werden auf schmalen Displays zu beschrifteten Karten. Das Desktop-Layout bleibt unverändert.

## Warum ist das Panel nur für Admins sichtbar?

Finanzdaten sind sensibel. Deshalb ist `panel_admin: true` gesetzt. Multi-User und rollenbasierte Rechte sind bewusst nicht in v1 enthalten.

## Welche Beträge kann ich eingeben?

Ganzzahlige Cent, also maximal zwei Nachkommastellen. Deutsche Schreibweisen wie `1.234,56`, `1234,56` oder `-42,31` werden akzeptiert. Drei Nachkommastellen werden abgelehnt statt gerundet. Der Betrag ist auf ±10 Milliarden Euro begrenzt.

## Wie ändere ich die Währung?

Die Währung wird pro Konto beim Anlegen gespeichert (Standard `EUR`). Die Anzeige verwendet die Währung des Kontos beziehungsweise `EUR` für Gesamtsummen. Weitere Währungen mit Umrechnung sind für v1 nicht vorgesehen.

## Warum lässt sich ein Konto mit Buchungen nicht löschen?

Das würde die Buchungen verwaist lassen. Konto und Buchungen müssen zuerst konsistent aufgeräumt werden; dasselbe gilt für Fixkosten-Regeln und Umbuchungen, die das Konto verwenden. Die Oberfläche zeigt dann einen entsprechenden Hinweis.

## Wie funktionieren die automatischen Buchungen bei Fixkosten?

Die Regeln unter **Fixkosten** enthalten nur Name, Betrag, Intervall und Fälligkeitsdatum. Beim Start des Add-ons und bei jedem Zugriff prüft Finance, welche Termine fällig sind, und legt daraus ganz normale Buchungen an. Ein eindeutiger Schlüssel verhindert Duplikate. Details: [fixkosten.md](fixkosten.md).

## Wie funktionieren Umbuchungen zwischen Konten?

Unter **Umbuchungen** legst du fest, von welchem Konto wie viel auf welches andere Konto verschoben wird. Finance erzeugt daraus zwei verknüpfte Buchungen: eine Ausgabe im Quellkonto und eine Einnahme im Zielkonto. Der Gesamtsaldo bleibt dadurch gleich. Umbuchungen werden nicht als Einnahme/Ausgabe gewertet und tauchen daher nicht in Budgets oder Kategorie-Auswertungen auf. Details: [umbuchungen.md](umbuchungen.md).

## Wie komme ich an meine Daten, wenn das Add-on nicht startet?

Am einfachsten über den Menüpunkt **Backups**: Dort lässt sich die Datenbank direkt als SQLite-Datei herunterladen oder eine Kopie speichern und später laden. Die Dateien liegen unter `/data/finance.db` beziehungsweise `/data/backups` und sind normale SQLite-Dateien; alternativ funktionieren ein Home-Assistant-Backup oder der Dateizugriff auf das Gerät. Details: [backup.md](backup.md).

## Gibt es eine Schnittstelle für andere Programme?

Innerhalb des Containers gibt es eine interne HTTP-API (`/api/...`). Sie ist nicht nach außen erreichbar und keine öffentliche, stabile Schnittstelle. Für einen Export von Daten steht der Menüpunkt **Backups** mit dem SQLite-Download zur Verfügung.

## Unterstützt das Add-on Home Assistant Core oder Container?

Das Image wird für HA OS gebaut und getestet. Die Ingress-Oberfläche setzt den Supervisor voraus; ohne Supervisor gibt es keine Sidebar und keine Authentifizierung.
