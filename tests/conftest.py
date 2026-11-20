"""Gemeinsame Fixtures: jeder Test läuft gegen eine frische SQLite-Datei."""

from __future__ import annotations

from pathlib import Path

import pytest
from main import app
from starlette.testclient import TestClient


@pytest.fixture
def db_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "finance.db"
    monkeypatch.setenv("FINANCE_DB_PATH", str(path))
    monkeypatch.setenv("FINANCE_RESTRICT_INGRESS", "0")
    return path


@pytest.fixture
def client(db_path: Path) -> TestClient:
    with TestClient(app) as test_client:
        yield test_client
