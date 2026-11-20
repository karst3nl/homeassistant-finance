"""Tests für den konsistenten SQLite-Snapshot der HA-Backups."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import backup
from db import init_db
from starlette.testclient import TestClient


def test_snapshot_enthaelt_daten_und_wird_entfernt(client: TestClient, db_path: Path) -> None:
    response = client.post("/api/accounts", json={"name": "Giro", "type": "checking"})
    assert response.status_code == 201, response.text

    backup.create_snapshot()
    target = backup.snapshot_path(db_path)
    assert target.is_file()

    with sqlite3.connect(target) as connection:
        names = [row[0] for row in connection.execute("SELECT name FROM accounts")]
    assert names == ["Giro"]

    backup.remove_snapshot()
    assert not target.exists()


def test_snapshot_ohne_wal_dateien(db_path: Path) -> None:
    init_db(db_path)
    for suffix in ("-wal", "-shm"):
        Path(str(db_path) + suffix).unlink(missing_ok=True)

    backup.create_snapshot()

    assert backup.snapshot_path(db_path).is_file()


def test_snapshot_ohne_datenbank_ist_harmlos(db_path: Path) -> None:
    assert not db_path.exists()

    backup.create_snapshot()
    backup.remove_snapshot()

    assert not backup.snapshot_path(db_path).exists()


def test_cli_akzeptiert_nur_pre_und_post() -> None:
    assert backup.main([]) == 2
    assert backup.main(["unknown"]) == 2
