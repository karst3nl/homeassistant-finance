"""Smoke-Tests für Einstieg und Ingress-Sperre."""

from __future__ import annotations

from pathlib import Path

import pytest
from main import SUPERVISOR_IP, app
from starlette.testclient import TestClient


def test_index(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "Finanzen" in response.text


def test_healthz(client: TestClient) -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.text == "ok"


def test_unbekannte_ip_wird_abgewiesen(monkeypatch: pytest.MonkeyPatch, db_path: Path) -> None:
    monkeypatch.setenv("FINANCE_RESTRICT_INGRESS", "1")

    with TestClient(app, client=("10.0.0.5", 12345)) as test_client:
        assert test_client.get("/").status_code == 403
        assert test_client.get("/api/accounts").status_code == 403


def test_supervisor_ip_darf_zugreifen(monkeypatch: pytest.MonkeyPatch, db_path: Path) -> None:
    monkeypatch.setenv("FINANCE_RESTRICT_INGRESS", "1")

    with TestClient(app, client=(SUPERVISOR_IP, 12345)) as test_client:
        assert test_client.get("/healthz").status_code == 200
        assert test_client.get("/api/accounts").status_code == 200
