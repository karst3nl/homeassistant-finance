# Sicherheitsrichtlinie

## Unterstützte Versionen

| Version | Unterstützt |
|---|---|
| 0.9.x (Release-Kandidat für 1.0) | Ja |
| < 0.9 | Nein |

Nach der Veröffentlichung von 1.0 wird die jeweils aktuelle Minor-Version unterstützt.

## Schwachstelle melden

Bitte **keine** öffentlichen Issues für sicherheitsrelevante Funde anlegen. Nutze stattdessen auf GitHub die Funktion **Report a vulnerability** unter dem Reiter *Security* dieses Repositories. Alternativ: Issue mit dem Hinweis, dass der Detailbericht privat erbeten wird – weitere Kommunikation erfolgt dann nicht öffentlich.

Bitte möglichst angeben:

- betroffene Version und Architektur
- Schritte zur Reproduktion
- erwartetes und tatsächliches Verhalten
- mögliche Auswirkung

Wir bestätigen den Eingang, sobald möglich, und informieren über den Stand der Behebung.

## Scope

Finance läuft vollständig lokal und ohne Netzwerkzugriff nach außen. Relevante Bereiche sind insbesondere:

- Ingress-Zugriffsschutz und Header-Validierung
- Eingabevalidierung und Cent-Arithmetik
- SQLite-Snapshot und Backup-Dateien
- Abhängigkeiten im Dockerfile

Die Abhängigkeiten werden bei jedem Push und wöchentlich mit `pip-audit` geprüft (`.github/workflows/security.yaml`); Dependabot hält pip- und Actions-Versionen aktuell.
