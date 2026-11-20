"""Tests für wiederkehrende Buchungen (Fixkosten)."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest
import recurring
from db import connect, init_db
from main import app
from recurring import RecurringError, add_months, next_due_date
from starlette.testclient import TestClient

MIGRATION_001 = (
    Path(__file__).resolve().parents[1]
    / "addons"
    / "finance"
    / "app"
    / "migrations"
    / "001_initial.sql"
)


def create_account(client: TestClient, name: str = "Giro") -> dict:
    response = client.post("/api/accounts", json={"name": name, "type": "checking"})
    assert response.status_code == 201, response.text
    return response.json()


def create_category(client: TestClient, name: str, kind: str = "expense") -> dict:
    response = client.post("/api/categories", json={"name": name, "type": kind})
    assert response.status_code == 201, response.text
    return response.json()


def rule_payload(account_id: int, **extra: object) -> dict:
    return {
        "name": "Miete",
        "amount_cents": 100000,
        "direction": "expense",
        "interval": "monthly",
        "account_id": account_id,
        "start_date": date.today().replace(day=1).isoformat(),
        **extra,
    }


def test_monatsgrenzen_und_schaltjahre() -> None:
    assert add_months(date(2024, 1, 31), 1) == date(2024, 2, 29)
    assert add_months(date(2023, 1, 31), 1) == date(2023, 2, 28)
    assert add_months(date(2026, 12, 15), 2) == date(2027, 2, 15)
    assert next_due_date(date(2024, 2, 29), "monthly") == date(2024, 3, 29)
    assert next_due_date(date(2024, 2, 29), "yearly") == date(2025, 2, 28)
    with pytest.raises(RecurringError):
        next_due_date(date.today(), "weekly")


def test_regel_crud_ueber_api(client: TestClient) -> None:
    account = create_account(client)
    category = create_category(client, "Wohnen")
    payload = rule_payload(account["id"], category_id=category["id"], counterparty="Vermieter")

    created = client.post("/api/recurring", json=payload)
    assert created.status_code == 201, created.text
    rule = created.json()
    assert rule["name"] == "Miete"
    assert rule["amount_cents"] == 100000
    assert (
        rule["next_due"]
        == next_due_date(date.fromisoformat(payload["start_date"]), "monthly").isoformat()
    )
    assert rule["account_name"] == "Giro"
    assert rule["category_name"] == "Wohnen"

    assert [row["id"] for row in client.get("/api/recurring").json()] == [rule["id"]]
    assert client.get(f"/api/recurring/{rule['id']}").json()["counterparty"] == "Vermieter"

    updated = client.put(f"/api/recurring/{rule['id']}", json={"amount_cents": 105000})
    assert updated.status_code == 200
    assert updated.json()["amount_cents"] == 105000
    assert updated.json()["name"] == "Miete"

    assert client.delete(f"/api/recurring/{rule['id']}").status_code == 204
    assert client.get(f"/api/recurring/{rule['id']}").status_code == 404


def test_faellige_buchungen_entstehen_nur_einmal(client: TestClient) -> None:
    account = create_account(client)
    created = client.post("/api/recurring", json=rule_payload(account["id"]))
    assert created.status_code == 201, created.text

    bookings = client.get("/api/transactions").json()
    assert len(bookings) == 1
    assert bookings[0]["amount_cents"] == -100000
    assert bookings[0]["source"] == "recurring"
    assert bookings[0]["recurring_rule_id"] == created.json()["id"]

    assert recurring.generate_due() == 0
    assert recurring.generate_due() == 0
    assert len(client.get("/api/transactions").json()) == 1


def test_monatlich_und_jaehrlich_werden_nachgebucht(client: TestClient) -> None:
    account = create_account(client)
    today = date.today()
    start = today.replace(year=today.year - 1, month=today.month, day=1)

    monthly = client.post(
        "/api/recurring",
        json=rule_payload(account["id"], name="Monat", start_date=start.isoformat()),
    )
    yearly = client.post(
        "/api/recurring",
        json=rule_payload(
            account["id"],
            name="Jahr",
            interval="yearly",
            start_date=start.isoformat(),
        ),
    )
    assert monthly.status_code == 201, monthly.text
    assert yearly.status_code == 201, yearly.text

    bookings = client.get("/api/transactions?limit=1000").json()
    from_monthly = [row for row in bookings if row["recurring_rule_id"] == monthly.json()["id"]]
    from_yearly = [row for row in bookings if row["recurring_rule_id"] == yearly.json()["id"]]
    assert len(from_monthly) == 13
    assert len(from_yearly) == 2
    assert from_monthly[-1]["booking_date"] == start.isoformat()
    assert from_yearly[-1]["booking_date"] == start.isoformat()


def test_pausierte_regeln_buchen_nicht(client: TestClient) -> None:
    account = create_account(client)
    past = (date.today() - timedelta(days=90)).isoformat()
    created = client.post(
        "/api/recurring", json=rule_payload(account["id"], active=False, start_date=past)
    )
    assert created.status_code == 201, created.text
    assert client.get("/api/transactions").json() == []
    assert created.json()["next_due"] > date.today().isoformat()


def test_einnahme_und_geplante_summe(client: TestClient) -> None:
    account = create_account(client)
    income_category = create_category(client, "Gehalt", "income")

    client.post(
        "/api/recurring",
        json=rule_payload(
            account["id"],
            name="Gehalt",
            direction="income",
            category_id=income_category["id"],
        ),
    )
    client.post(
        "/api/recurring",
        json=rule_payload(
            account["id"],
            name="Versicherung",
            interval="yearly",
            amount_cents=120000,
        ),
    )

    bookings = client.get("/api/transactions").json()
    income_booking = next(row for row in bookings if row["amount_cents"] > 0)
    assert income_booking["amount_cents"] == 100000

    summary = recurring.planned_summary()
    assert summary["income_cents"] == 100000
    assert summary["expense_cents"] == 10000  # 120000 / 12
    assert summary["rule_count"] == 2

    monthly = client.get("/api/stats/monthly").json()
    assert monthly[-1]["income_cents"] == 100000


def test_ungueltige_regeln_werden_abgelehnt(client: TestClient) -> None:
    account = create_account(client)
    expense = create_category(client, "Wohnen")
    income = create_category(client, "Gehalt", "income")

    responses = [
        client.post("/api/recurring", json=rule_payload(account["id"], interval="weekly")),
        client.post("/api/recurring", json=rule_payload(account["id"], amount_cents=0)),
        client.post("/api/recurring", json=rule_payload(account["id"], amount_cents=-100)),
        client.post("/api/recurring", json=rule_payload(999)),
        client.post("/api/recurring", json=rule_payload(account["id"], direction="spenden")),
        client.post("/api/recurring", json=rule_payload(account["id"], start_date="20.11.2026")),
        client.post("/api/recurring", json=rule_payload(account["id"], category_id=income["id"])),
        client.post(
            "/api/recurring",
            json=rule_payload(account["id"], direction="income", category_id=expense["id"]),
        ),
        client.get("/api/recurring/abc"),
    ]
    assert all(response.status_code == 400 for response in responses)


def test_loeschen_der_regel_laesst_buchungen(client: TestClient) -> None:
    account = create_account(client)
    created = client.post("/api/recurring", json=rule_payload(account["id"]))
    rule_id = created.json()["id"]
    assert len(client.get("/api/transactions").json()) == 1

    assert client.delete(f"/api/recurring/{rule_id}").status_code == 204
    bookings = client.get("/api/transactions").json()
    assert len(bookings) == 1
    assert bookings[0]["recurring_rule_id"] is None


def test_migration_erweitert_bestehende_datenbank(db_path: Path) -> None:
    connection = connect(db_path)
    connection.executescript(MIGRATION_001.read_text(encoding="utf-8"))
    connection.execute("INSERT INTO accounts (name, type) VALUES ('Alt', 'checking')")
    connection.commit()
    connection.close()

    init_db(db_path)

    with connect(db_path) as connection:
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(transactions)")}
        assert "recurring_rule_id" in columns
        assert "recurring_period" in columns
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 2
        assert connection.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] == 1


def test_start_und_next_due_bleiben_bei_neustart(db_path: Path) -> None:
    with TestClient(app) as first:
        account = create_account(first)
        rule = first.post("/api/recurring", json=rule_payload(account["id"])).json()
        rule_id = rule["id"]

    with TestClient(app) as second:
        stored = second.get(f"/api/recurring/{rule_id}").json()
        assert stored["start_date"] == rule["start_date"]
        assert stored["next_due"] == rule["next_due"]
        assert len(second.get("/api/transactions").json()) == 1
