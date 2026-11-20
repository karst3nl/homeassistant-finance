"""Tests für die Auswertungs- und Budget-Seiten."""

from __future__ import annotations

from reports import current_period
from starlette.testclient import TestClient


def prepare(client: TestClient) -> None:
    client.post(
        "/ui/accounts", data={"name": "Giro", "type": "checking", "initial_balance": "100,00"}
    )
    client.post("/ui/categories", data={"name": "Lebensmittel", "type": "expense"})
    client.post(
        "/ui/transactions",
        data={
            "direction": "expense",
            "booking_date": "2026-11-10",
            "account_id": "1",
            "amount": "12,34",
            "counterparty": "REWE",
            "category_id": "1",
        },
    )


def test_auswertungsseite_zeigt_charts_und_kennzahlen(client: TestClient) -> None:
    prepare(client)
    client.post(
        "/ui/budgets",
        data={"category_id": "1", "period": "2026-11", "limit": "20,00"},
        follow_redirects=False,
    )

    page = client.get("/ui/reports?period=2026-11")
    assert page.status_code == 200
    assert "November 2026" in page.text
    assert "Monatsvergleich" in page.text
    assert "Ausgaben nach Kategorie" in page.text
    assert "Saldo-Verlauf" in page.text
    assert "<svg" in page.text
    assert "Lebensmittel" in page.text
    assert "12,34 EUR" in page.text
    assert "87,66 EUR" in page.text
    assert "progress-fill" in page.text
    assert "ui/reports?period=2026-10" in page.text


def test_budgets_ueber_ui_anlegen_aendern_und_loeschen(client: TestClient) -> None:
    prepare(client)
    created = client.post(
        "/ui/budgets",
        data={"category_id": "1", "period": "2026-11", "limit": "20,00"},
        follow_redirects=False,
    )
    assert created.status_code == 303
    assert created.headers["location"] == "/ui/budgets?period=2026-11"

    page = client.get("/ui/budgets?period=2026-11")
    assert "20,00 EUR" in page.text
    assert "12,34 EUR" in page.text

    updated = client.post(
        "/ui/budgets/1",
        data={"period": "2026-11", "limit": "25,00"},
        follow_redirects=False,
    )
    assert updated.status_code == 303
    assert "25,00 EUR" in client.get("/ui/budgets?period=2026-11").text

    deleted = client.post(
        "/ui/budgets/1/delete",
        data={"period": "2026-11"},
        follow_redirects=False,
    )
    assert deleted.status_code == 303
    assert "Noch keine Budgets" in client.get("/ui/budgets?period=2026-11").text


def test_budget_fehler_werden_angezeigt(client: TestClient) -> None:
    prepare(client)
    invalid = client.post(
        "/ui/budgets",
        data={"category_id": "1", "period": "2026-11", "limit": "abc"},
    )
    assert invalid.status_code == 400
    assert "Bitte einen gültigen Betrag angeben" in invalid.text

    client.post(
        "/ui/budgets",
        data={"category_id": "1", "period": "2026-11", "limit": "20,00"},
        follow_redirects=False,
    )
    duplicate = client.post(
        "/ui/budgets",
        data={"category_id": "1", "period": "2026-11", "limit": "30,00"},
    )
    assert duplicate.status_code == 400
    assert "schon ein Budget" in duplicate.text


def test_dashboard_zeigt_budget_des_aktuellen_monats(client: TestClient) -> None:
    prepare(client)
    client.post(
        "/ui/budgets",
        data={"category_id": "1", "period": current_period(), "limit": "50,00"},
        follow_redirects=False,
    )
    page = client.get("/")
    assert "Budgets diesen Monat" in page.text
    assert "Lebensmittel" in page.text
    assert "progress-fill" in page.text


def test_ingress_pfad_auf_neuen_seiten(client: TestClient) -> None:
    headers = {"X-Ingress-Path": "/api/hassio_ingress/tok/"}
    for path in ("/ui/reports", "/ui/budgets"):
        page = client.get(path, headers=headers)
        assert page.status_code == 200
        assert '<base href="/api/hassio_ingress/tok/" />' in page.text
