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


def test_backup_seite_und_aktiver_menupunkt(client: TestClient) -> None:
    page = client.get("/ui/backups")

    assert page.status_code == 200
    assert 'class="active" aria-current="page">Backups</a>' in page.text
    assert "Noch keine Backups vorhanden" in page.text
    assert 'href="ui/backups/download"' in page.text
    assert 'action="ui/backups"' in page.text


def test_backup_speichern_herunterladen_und_loeschen(
    client: TestClient, db_path: Path, tmp_path: Path
) -> None:
    assert (
        client.post("/api/accounts", json={"name": "Giro", "type": "checking"}).status_code == 201
    )

    response = client.post("/ui/backups", follow_redirects=False)
    assert response.status_code == 303, response.text
    assert response.headers["location"] == "/ui/backups"

    page = client.get("/ui/backups").text
    assert "Noch keine Backups vorhanden" not in page
    item = backup.list_backups()[0]
    assert item["name"] in page
    assert item["created"] in page

    download = client.get(f"/ui/backups/{item['name']}/download")
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/x-sqlite3"
    assert f'attachment; filename="{item["name"]}"' in download.headers["content-disposition"]
    assert download.content.startswith(b"SQLite format 3")

    saved = tmp_path / "heruntergeladen.db"
    saved.write_bytes(download.content)
    with sqlite3.connect(saved) as connection:
        names = [row[0] for row in connection.execute("SELECT name FROM accounts")]
    assert names == ["Giro"]

    delete = client.post(f"/ui/backups/{item['name']}/delete", follow_redirects=False)
    assert delete.status_code == 303
    assert "Noch keine Backups vorhanden" in client.get("/ui/backups").text
    assert backup.list_backups() == []


def test_direkter_download_legt_nichts_ab(client: TestClient) -> None:
    assert (
        client.post("/api/accounts", json={"name": "Giro", "type": "checking"}).status_code == 201
    )

    response = client.get("/ui/backups/download")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/x-sqlite3"
    assert "attachment;" in response.headers["content-disposition"]
    assert response.content.startswith(b"SQLite format 3")
    assert backup.list_backups() == []


def test_unbekannte_oder_ungueltige_backups_werden_abgelehnt(client: TestClient) -> None:
    names = (
        "finance-20261120-154500-aaaaaaaa.db",  # gültiges Format, nicht vorhanden
        "finance.db",
        "../finance.db",
        "..%2Ffinance.db",
        "finance-20261120-154500-aaaaaaaa.db.tmp",
    )
    for name in names:
        assert client.get(f"/ui/backups/{name}/download").status_code == 404, name
        assert client.post(f"/ui/backups/{name}/delete").status_code == 404, name

    assert backup.backup_path("../finance.db") is None
    assert backup.delete_backup("../finance.db") is False
