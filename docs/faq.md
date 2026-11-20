# Häufige Fragen

## Warum sehe ich keine Sensoren oder Entitäten in Home Assistant?

Das Add-on ist bewusst eine „reine UI": Es gibt keine HA-Entitäten, keine MQTT-Themen und keine Automatisierungen. Die Daten bleiben in der SQLite-Datei des Add-ons und werden nur in dessen Ingress-Oberfläche angezeigt.

## Werden meine Bankkonten automatisch abgefragt?

Nein. v1 unterstützt ausschließlich manuelle Erfassung. Es gibt keine Bankverbindung, kein FinTS/HBCI und keinen CSV-Import.

## Warum ist das Panel nur für Admins sichtbar?

Finanzdaten sind sensibel. Deshalb ist `panel_admin: true` gesetzt. Multi-User und rollenbasierte Rechte sind bewusst nicht in v1 enthalten.

## Welche Beträge kann ich eingeben?

Ganzzahlige Cent, also maximal zwei Nachkommastellen. Deutsche Schreibweisen wie `1.234,56`, `1234,56` oder `-42,31` werden akzeptiert. Drei Nachkommastellen werden abgelehnt statt gerundet. Der Betrag ist auf ±10 Milliarden Euro begrenzt.

## Wie ändere ich die Währung?

Die Währung wird pro Konto beim Anlegen gespeichert (Standard `EUR`). Die Anzeige verwendet die Währung des Kontos beziehungsweise `EUR` für Gesamtsummen. Weitere Währungen mit Umrechnung sind für v1 nicht vorgesehen.

## Warum lässt sich ein Konto mit Buchungen nicht löschen?

Das würde die Buchungen verwaist lassen. Konto und Buchungen müssen zuerst konsistent aufgeräumt werden; die Oberfläche zeigt dann einen entsprechenden Hinweis.

## Wie komme ich an meine Daten, wenn das Add-on nicht startet?

Die Datenbank liegt unter `/data/finance.db`. Über ein Home-Assistant-Backup oder den Dateizugriff auf das Gerät lässt sie sich kopieren. Sie ist eine normale SQLite-Datei.

## Gibt es eine Schnittstelle für andere Programme?

Innerhalb des Containers gibt es eine interne HTTP-API (`/api/...`). Sie ist nicht nach außen erreichbar und keine öffentliche, stabile Schnittstelle. Für Exporte ist in einer späteren Version ein Dateiexport geplant.

## Unterstützt das Add-on Home Assistant Core oder Container?

Das Image wird für HA OS gebaut und getestet. Die Ingress-Oberfläche setzt den Supervisor voraus; ohne Supervisor gibt es keine Sidebar und keine Authentifizierung.
