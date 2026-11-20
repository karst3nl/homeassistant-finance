"""Integrationstests für die CRUD-API gegen eine echte SQLite-Datei."""

from __future__ import annotations

from pathlib import Path

from main import app
from starlette.testclient import TestClient


def create_account(client: TestClient, name: str = "Giro", **extra: object) -> dict:
    response = client.post("/api/accounts", json={"name": name, "type": "checking", **extra})
    assert response.status_code == 201, response.text
    return response.json()


def create_category(client: TestClient, name: str = "Lebensmittel", **extra: object) -> dict:
    response = client.post("/api/categories", json={"name": name, "type": "expense", **extra})
    assert response.status_code == 201, response.text
    return response.json()


def create_transaction(client: TestClient, account_id: int, **extra: object) -> dict:
    payload = {"account_id": account_id, "booking_date": "2026-11-18", "amount_cents": 1000}
    payload.update(extra)
    response = client.post("/api/transactions", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_konten_crud(client: TestClient) -> None:
    created = create_account(client, initial_balance_cents=100000)
    account_id = created["id"]
    assert created["currency"] == "EUR"
    assert created["active"] == 1
    assert created["initial_balance_cents"] == 100000

    assert [row["id"] for row in client.get("/api/accounts").json()] == [account_id]
    assert client.get(f"/api/accounts/{account_id}").json()["name"] == "Giro"

    updated = client.put(f"/api/accounts/{account_id}", json={"name": "Giro neu", "active": False})
    assert updated.status_code == 200
    assert updated.json()["name"] == "Giro neu"
    assert updated.json()["active"] == 0

    assert client.delete(f"/api/accounts/{account_id}").status_code == 204
    assert client.get(f"/api/accounts/{account_id}").status_code == 404


def test_kategorien_crud(client: TestClient) -> None:
    parent = create_category(client, name="Ausgaben")
    child = create_category(
        client,
        parent_id=parent["id"],
        color="#ff0000",
        icon="mdi:cart",
    )
    assert child["parent_id"] == parent["id"]
    assert child["color"] == "#ff0000"

    updated = client.put(f"/api/categories/{child['id']}", json={"name": "Lebensmittel & Haus"})
    assert updated.status_code == 200
    assert updated.json()["name"] == "Lebensmittel & Haus"
    assert updated.json()["parent_id"] == parent["id"]

    assert client.delete(f"/api/categories/{child['id']}").status_code == 204
    assert client.get(f"/api/categories/{child['id']}").status_code == 404


def test_buchungen_crud_mit_cent_arithmetik(client: TestClient) -> None:
    account = create_account(client)
    category = create_category(client)

    created = create_transaction(
        client,
        account["id"],
        amount="-42,31",
        counterparty="REWE",
        description="Wocheneinkauf",
        category_id=category["id"],
    )
    transaction_id = created["id"]
    assert created["amount_cents"] == -4231
    assert created["source"] == "manual"
    assert created["counterparty"] == "REWE"

    listed = client.get("/api/transactions").json()
    assert [row["id"] for row in listed] == [transaction_id]
    assert client.get("/api/transactions?date_from=2026-11-01&date_to=2026-11-30").json() == listed
    assert client.get("/api/transactions?date_from=2026-12-01").json() == []
    assert len(client.get(f"/api/transactions?account_id={account['id']}").json()) == 1
    assert len(client.get(f"/api/transactions?category_id={category['id']}").json()) == 1

    updated = client.put(
        f"/api/transactions/{transaction_id}",
        json={"amount": "0,01", "description": "Korrektur"},
    )
    assert updated.status_code == 200
    assert updated.json()["amount_cents"] == 1
    assert updated.json()["description"] == "Korrektur"
    assert updated.json()["updated_at"] != created["updated_at"]

    assert client.delete(f"/api/transactions/{transaction_id}").status_code == 204
    assert client.get(f"/api/transactions/{transaction_id}").status_code == 404


def test_budgets_crud(client: TestClient) -> None:
    category = create_category(client)
    created = client.post(
        "/api/budgets",
        json={"category_id": category["id"], "period": "2026-11", "limit_cents": 20000},
    )
    assert created.status_code == 201, created.text
    budget_id = created.json()["id"]

    listed = client.get("/api/budgets?period=2026-11").json()
    assert [row["id"] for row in listed] == [budget_id]
    assert listed[0]["category_name"] == "Lebensmittel"

    updated = client.put(f"/api/budgets/{budget_id}", json={"limit_cents": 25000})
    assert updated.status_code == 200
    assert updated.json()["limit_cents"] == 25000

    assert client.delete(f"/api/budgets/{budget_id}").status_code == 204
    assert client.get(f"/api/budgets/{budget_id}").status_code == 404


def test_eingaben_werden_validiert(client: TestClient) -> None:
    account = create_account(client)
    create_transaction(client, account["id"], amount_cents=1000)
    base = {"account_id": account["id"], "booking_date": "2026-11-18"}

    assert (
        client.post(
            "/api/transactions", json={**base, "account_id": 999, "amount_cents": 100}
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/transactions", json={**base, "booking_date": "18.11.2026", "amount_cents": 100}
        ).status_code
        == 400
    )
    assert client.post("/api/transactions", json={**base, "amount": "1,234"}).status_code == 201
    assert client.post("/api/transactions", json={**base, "amount": "1,2345"}).status_code == 400
    assert client.get("/api/accounts/abc").status_code == 400
    assert client.post("/api/categories", json={"name": "X", "type": "unknown"}).status_code == 400

    assert client.delete(f"/api/accounts/{account['id']}").status_code == 409


def test_doppelte_budgets_werden_abgelehnt(client: TestClient) -> None:
    category = create_category(client)
    payload = {"category_id": category["id"], "period": "2026-11", "limit_cents": 100}
    assert client.post("/api/budgets", json=payload).status_code == 201
    assert client.post("/api/budgets", json=payload).status_code == 409


def test_datenbank_ueberlebt_neustart(db_path: Path) -> None:
    with TestClient(app) as first:
        account = create_account(first, name="Dauerhaft")
        create_transaction(first, account["id"], amount_cents=1234)

    with TestClient(app) as second:
        accounts = second.get("/api/accounts").json()
        assert [row["name"] for row in accounts] == ["Dauerhaft"]
        transactions = second.get("/api/transactions").json()
        assert [row["amount_cents"] for row in transactions] == [1234]
