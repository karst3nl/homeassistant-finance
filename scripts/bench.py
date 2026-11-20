"""Kleiner lokaler Performance-Check ohne Home Assistant.

Misst die servergerenderte Oberfläche und die Statistik-API gegen eine
temporäre SQLite-Datenbank. Auf dem Raspberry Pi 4 zusätzlich manuell messen
(siehe docs/performance.md) – dieses Skript ist nur ein reproduzierbarer
Ausgangswert für die Entwicklung.

Aufruf: python scripts/bench.py
"""

from __future__ import annotations

import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    sys.path.insert(0, str(ROOT / "addons" / "finance" / "app"))
    with tempfile.TemporaryDirectory(prefix="finance-bench-") as directory:
        os.environ["FINANCE_DB_PATH"] = str(Path(directory) / "finance.db")
        os.environ["FINANCE_RESTRICT_INGRESS"] = "0"

        from main import app
        from starlette.testclient import TestClient

        with TestClient(app) as client:
            account = client.post("/api/accounts", json={"name": "Giro", "type": "checking"})
            assert account.status_code == 201, account.text
            category = client.post(
                "/api/categories", json={"name": "Lebensmittel", "type": "expense"}
            )
            category_id = category.json()["id"]

            for index in range(500):
                response = client.post(
                    "/api/transactions",
                    json={
                        "account_id": 1,
                        "booking_date": f"2026-11-{(index % 28) + 1:02d}",
                        "amount_cents": -(index + 1) * 13,
                        "category_id": category_id,
                        "counterparty": f"Händler {index % 20}",
                    },
                )
                assert response.status_code == 201, response.text

            targets = (
                ("Dashboard", "/"),
                ("Buchungen", "/ui/transactions"),
                ("Auswertungen", "/ui/reports"),
                ("Statistik-API", "/api/stats/monthly"),
            )
            print(f"{'Endpunkt':<16} {'n':>5} {'Median':>10} {'p95':>10} (ms)")
            for label, path in targets:
                samples: list[float] = []
                for _ in range(100):
                    start = time.perf_counter()
                    response = client.get(path)
                    samples.append((time.perf_counter() - start) * 1000)
                    assert response.status_code == 200, response.text
                samples.sort()
                median = statistics.median(samples)
                p95 = samples[94]
                print(f"{label:<16} {len(samples):>5} {median:>10.2f} {p95:>10.2f}")

            db_path = Path(os.environ["FINANCE_DB_PATH"])
            print(f"\nSQLite-Datei: {db_path.stat().st_size / 1024:.0f} KiB (500 Buchungen)")


if __name__ == "__main__":
    main()
