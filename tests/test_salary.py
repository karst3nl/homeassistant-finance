"""Tests für das Monatsgehalt als eigenen Bereich."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import salary
from db import connect, init_db
from main import app
from starlette.testclient import TestClient

MIGRATION_001 = (
    Path(__file__).resolve().parents[1]
    / "addons"
    / "finance"
    / "app"
    / "migrations"
    / "001_initial.sql"
)


def create_account(client: TestClient, name: str = "Giro", initial_cents: int = 0) -> dict:
    response = client.post(
        "/api/accounts",
        json={"name": name, "type": "checking", "initial_balance_cents": initial_cents},
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_category(client: TestClient, name: str = "Gehalt", kind: str = "income") -> dict:
    response = client.post("/api/categories", json={"name": name, "type": kind})
    assert response.status_code == 201, response.text
    return response.json()


def payload(account_id: int, category_id: int | None = None, **extra: object) -> dict:
    return {
        "name": "Monatsgehalt",
        "amount_cents": 250000,
        "account_id": account_id,
        "category_id": category_id,
        "start_date": date.today().replace(day=1).isoformat(),
        "counterparty": "Arbeitgeber GmbH",
        **extra,
    }


def test_gehaltsregel_crud_ueber_api(client: TestClient) -> None:
    account = create_account(client)
    category = create_category(client)

    created = client.post("/api/salary", json=payload(account["id"], category["id"]))
    assert created.status_code == 201, created.text
    rule = created.json()
    assert rule["name"] == "Monatsgehalt"
    assert rule["amount_cents"] == 250000
    assert rule["account_name"] == "Giro"
    assert rule["category_name"] == "Gehalt"
    assert rule["active"] == 1

    assert [item["id"] for item in client.get("/api/salary").json()] == [rule["id"]]
    assert client.get(f"/api/salary/{rule['id']}").json()["counterparty"] == "Arbeitgeber GmbH"

    updated = client.put(f"/api/salary/{rule['id']}", json={"amount_cents": 260000})
    assert updated.status_code == 200, updated.text
    assert updated.json()["amount_cents"] == 260000
    assert updated.json()["start_date"] == rule["start_date"]
    assert updated.json()["next_due"] == rule["next_due"]

    assert client.delete(f"/api/salary/{rule['id']}").status_code == 204
    assert client.get(f"/api/salary/{rule['id']}").status_code == 404
    assert client.get("/api/salary").json() == []


def test_gehalt_wird_monatlich_und_idempotent_gebucht(client: TestClient, db_path: Path) -> None:
    account = create_account(client)
    category = create_category(client)
    rule_id = salary.create_rule(payload(account["id"], category["id"], start_date="2026-08-31"))

    assert salary.generate_due(date(2026, 11, 20)) == 3
    assert salary.generate_due(date(2026, 11, 20)) == 0

    with connect(db_path) as connection:
        rows = [dict(row) for row in connection.execute("SELECT * FROM transactions ORDER BY id")]
    assert [row["salary_period"] for row in rows] == ["2026-08", "2026-09", "2026-10"]
    assert [row["booking_date"] for row in rows] == ["2026-08-31", "2026-09-30", "2026-10-30"]
    assert all(row["amount_cents"] == 250000 for row in rows)
    assert all(row["source"] == "salary" for row in rows)
    assert all(row["salary_rule_id"] == rule_id for row in rows)
    assert all(row["counterparty"] == "Arbeitgeber GmbH" for row in rows)

    rule = salary.get_rule(rule_id)
    assert rule is not None
    assert rule["next_due"] == "2026-11-30"


def test_pausiertes_gehalt_rueckt_next_due_ohne_buchung(client: TestClient) -> None:
    account = create_account(client)
    rule_id = salary.create_rule(payload(account["id"], start_date="2026-08-31", active=0))

    assert salary.generate_due(date(2026, 11, 20)) == 0
    rule = salary.get_rule(rule_id)
    assert rule is not None
    assert rule["next_due"] == "2026-11-30"
    assert salary.planned_summary()["monthly_cents"] == 0


def test_gehalt_zaehlt_als_einnahme(client: TestClient) -> None:
    account = create_account(client)
    category = create_category(client)
    created = client.post("/api/salary", json=payload(account["id"], category["id"]))
    assert created.status_code == 201, created.text

    rows = client.get("/api/stats/monthly?months=1").json()
    assert rows[-1]["income_cents"] >= 250000
    categories = client.get("/api/stats/categories?type=income").json()
    assert categories[0]["name"] == "Gehalt"


def test_ungueltige_gehaltsregeln_werden_abgelehnt(client: TestClient) -> None:
    account = create_account(client)
    expense = create_category(client, "Lebensmittel", "expense")
    valid = payload(account["id"], expense["id"])

    invalid = (
        {**valid, "amount_cents": 0},
        {**valid, "amount_cents": -100},
        {**valid, "account_id": 999},
        {**valid, "start_date": "kein-datum"},
        {**valid, "name": "   "},
        {**valid, "category_id": 999},
    )
    for item in invalid:
        response = client.post("/api/salary", json=item)
        assert response.status_code == 400, (item, response.text)

    # Eine Ausgabe-Kategorie passt nicht zu Einnahmen.
    assert client.post("/api/salary", json=valid).status_code == 400


def test_delete_laesst_bereits_erzeugte_buchungen(client: TestClient) -> None:
    account = create_account(client)
    created = client.post("/api/salary", json=payload(account["id"]))
    assert created.status_code == 201, created.text
    rule_id = created.json()["id"]

    bookings = client.get("/api/transactions").json()
    assert len(bookings) == 1
    assert bookings[0]["source"] == "salary"

    assert client.delete(f"/api/salary/{rule_id}").status_code == 204
    bookings = client.get("/api/transactions").json()
    assert len(bookings) == 1
    assert bookings[0]["salary_rule_id"] is None


def test_gehaltsseite_und_formular(client: TestClient) -> None:
    account = create_account(client)
    category = create_category(client)

    page = client.get("/ui/salary")
    assert page.status_code == 200
    assert 'class="active" aria-current="page">Monatsgehalt</a>' in page.text
    assert "Noch kein Monatsgehalt hinterlegt." in page.text
    assert 'action="ui/salary"' in page.text

    form = {
        "name": "Monatsgehalt",
        "amount": "2500,00",
        "account_id": str(account["id"]),
        "category_id": str(category["id"]),
        "start_date": date.today().replace(day=1).isoformat(),
        "counterparty": "Arbeitgeber GmbH",
        "description": "",
        "active": "1",
    }
    created = client.post("/ui/salary", data=form, follow_redirects=False)
    assert created.status_code == 303, created.text
    assert created.headers["location"] == "/ui/salary"

    page = client.get("/ui/salary").text
    assert "Noch kein Monatsgehalt hinterlegt." not in page
    assert "Arbeitgeber GmbH" in page
    assert "2.500,00 EUR" in page
    assert 'href="ui/salary/1/edit"' in page

    edit = client.get("/ui/salary/1/edit")
    assert edit.status_code == 200
    assert "Gehalt bearbeiten" in edit.text

    updated = client.post(
        "/ui/salary/1", data={**form, "amount": "2600,00"}, follow_redirects=False
    )
    assert updated.status_code == 303
    assert "2.600,00 EUR" in client.get("/ui/salary").text

    deleted = client.post("/ui/salary/1/delete", follow_redirects=False)
    assert deleted.status_code == 303
    assert "Noch kein Monatsgehalt hinterlegt." in client.get("/ui/salary").text


def test_gehalt_und_next_due_bleiben_bei_neustart(db_path: Path) -> None:
    with TestClient(app) as first:
        account = create_account(first)
        created = first.post("/api/salary", json=payload(account["id"]))
        assert created.status_code == 201, created.text
        rule = created.json()

    with TestClient(app) as second:
        stored = second.get(f"/api/salary/{rule['id']}").json()
        assert stored["start_date"] == rule["start_date"]
        assert stored["next_due"] == rule["next_due"]
        assert len(second.get("/api/transactions").json()) == 1


def test_migration_erhaelt_bestehende_buchungen(db_path: Path) -> None:
    connection = connect(db_path)
    connection.executescript(MIGRATION_001.read_text(encoding="utf-8"))
    connection.execute("INSERT INTO accounts (name, type) VALUES ('Alt', 'checking')")
    connection.execute(
        "INSERT INTO transactions (account_id, booking_date, amount_cents) "
        "VALUES (1, '2026-11-01', -123)"
    )
    connection.commit()
    connection.close()

    init_db(db_path)

    with connect(db_path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 4
        tables = {
            row["name"]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        assert "salary_rules" in tables
        assert connection.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 1


def test_buchung_ist_als_monatsgehalt_gekennzeichnet(client: TestClient) -> None:
    account = create_account(client)
    assert client.post("/api/salary", json=payload(account["id"])).status_code == 201

    page = client.get("/ui/transactions").text
    assert "<small>Monatsgehalt</small>" in page
    assert "automatisch (Fixkosten)" not in page
