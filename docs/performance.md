# Performance

## Ziele

| Kennzahl | Ziel (Raspberry Pi 4) |
|---|---|
| Image-Größe | < 80 MB |
| RAM im Leerlauf | < 80 MB |
| Start bis `/healthz` | < 5 s |
| CPU im Leerlauf | ~0 % |
| Antwortzeit Oberfläche | < 100 ms typisch |

Der Pi 4 ist die langsamste unterstützte Plattform; `aarch64` wird als erstes gebaut und getestet.

## Reproduzierbarer Lokalwert

Mit installierten Dev-Abhängigkeiten:

```bash
python scripts/bench.py
```

Das Skript legt 500 Buchungen in einer temporären Datenbank an und misst 100 Anfragen je Endpunkt (Median und p95). Auf einem aktuellen Entwicklungsrechner lag der Median bei etwa:

| Endpunkt | Median | p95 |
|---|---:|---:|
| Dashboard | 1,1 ms | 1,4 ms |
| Buchungen | 2,4 ms | 2,7 ms |
| Auswertungen | 2,0 ms | 2,3 ms |
| Statistik-API | 0,8 ms | 1,0 ms |

SQLite-Datei mit 500 Buchungen: ca. 112 KiB. Das ist nur ein Ausgangswert – kein Ersatz für die Messung auf dem Pi.

## Messung auf dem Raspberry Pi 4 (manuell)

**Status:** noch nicht durchgeführt. Vor der Freigabe von v1.0.0 auf echter HA-OS-Installation nachholen.

1. Add-on installieren und starten.
2. Startzeit messen (Zeitpunkt „Start" bis erste erfolgreiche Antwort des Ingress):

   ```bash
   time curl -fsS "http://<IP>:8123/api/hassio_ingress/<TOKEN>/healthz"
   ```

   Die Ingress-URL und das Token stehen in den Add-on-Details in Home Assistant.

3. Speicherverbrauch des Containers ablesen (z. B. über `docker stats` auf Systemen mit Docker-Zugriff oder die HA-Systemmonitor-Integration).
4. Image-Größe prüfen:

   ```bash
   docker images ghcr.io/karst3nl/finance --format '{{.Size}}'
   ```

5. Oberfläche mit einigen hundert manuellen Buchungen füllen und die Ladezeit subjektiv sowie mit den Browser-Entwicklerwerkzeugen prüfen.
6. Backup erstellen und wiederherstellen (siehe [backup.md](backup.md)).

## Was die Schlankheit sichert

- Ein Python-Prozess (Uvicorn), kein Node, kein zweiter Webserver
- Kein Build-Step im Container, keine Frontend-Abhängigkeiten
- Serverseitig erzeugtes HTML und SVG, kein JavaScript, keine CDNs
- Eine SQLite-Datei mit WAL und Indizes auf Datum/Fremdschlüsseln
- Pinning der Laufzeit-Abhängigkeiten und Alpine-Basisimage

Wenn eine Messung die Ziele verfehlt, zuerst die Anzahl der Buchungen und die Chart-Berechnung prüfen, bevor die Architektur geändert wird.
