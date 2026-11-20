"""Tests für Umbuchungen zwischen Konten."""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import pytest
from db import connect, init_db
from reports import (
    balance_history,
    budget_progress,
    category_breakdown,
    current_period,
    monthly_comparison,
)
from starlette.testclient import TestClient
from stats import dashboard_data

MIGRATION_001 = (
    Path(__file__).resolve().parents[1]
    / "addons"
    / "finance"
    / "app"
    / "migrations"
    / "001_initial.sql"
)


def create_account(client: TestClient, name: str, initial_cents: int = 0) -> dict:
    response = client.post(
        "/api/accounts",
        json={"name": name, "type": "checking", "initial_balance_cents": initial_cents},
    )
    assert response.status_code == 201, response.text
    return response.json()


def transfer_payload(from_id: int, to_id: int, **extra: object) -> dict:
    return {
        "booking_date": "2026-11-20",
        "amount_cents": 25000,
        "from_account_id": from_id,
        "to_account_id": to_id,
        **extra,
    }


def balances(db_path: Path) -> dict[str, int]:
    with connect(db_path) as connection:
        rows = connection.execute(
            """SELECT a.name, a.initial_balance_cents + COALESCE(SUM(t.amount_cents), 0)
                      AS balance_cents
               FROM accounts a
               LEFT JOIN transactions t ON t.account_id = a.id
               GROUP BY a.id"""
        ).fetchall()
    return {row["name"]: row["balance_cents"] for row in rows}


def legs(client: TestClient, transfer_id: int) -> list[dict]:
    response = client.get(f"/api/transactions?transfer_id={transfer_id}&limit=1000")
    assert response.status_code == 200, response.text
    return response.json()


def test_umbuchung_erzeugt_konsistentes_buchungspaar(client: TestClient, db_path: Path) -> None:
    source = create_account(client, "Giro", 100000)
    target = create_account(client, "Sparkonto")

    created = client.post(
        "/api/transfers",
        json=transfer_payload(source["id"], target["id"], description="Dauerauftrag"),
    )
    assert created.status_code == 201, created.text
    transfer = created.json()
    assert transfer["amount_cents"] == 25000
    assert transfer["from_account_name"] == "Giro"
    assert transfer["to_account_name"] == "Sparkonto"

    booking = legs(client, transfer["id"])
    assert len(booking) == 2
    by_account = {row["account_id"]: row for row in booking}
    outgoing = by_account[source["id"]]
    incoming = by_account[target["id"]]
    assert outgoing["amount_cents"] == -25000
    assert incoming["amount_cents"] == 25000
    assert outgoing["source"] == incoming["source"] == "transfer"
    assert outgoing["category_id"] is incoming["category_id"] is None
    assert outgoing["counterparty"] == "nach Sparkonto"
    assert incoming["counterparty"] == "von Giro"
    assert outgoing["transfer_id"] == incoming["transfer_id"] == transfer["id"]

    assert balances(db_path) == {"Giro": 75000, "Sparkonto": 25000}

    # Ein zweiter Bein auf demselben Konto würde das Paar unbrauchbar machen.
    with connect(db_path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO transactions
                   (account_id, booking_date, amount_cents, source, transfer_id)
                   VALUES (?, '2026-11-20', -25000, 'transfer', ?)""",
                (source["id"], transfer["id"]),
            )
        connection.rollback()


def test_umbuchung_crud_und_aktualisierung(client: TestClient) -> None:
    first = create_account(client, "Giro", 100000)
    second = create_account(client, "Sparkonto")
    third = create_account(client, "Bargeld")

    created = client.post("/api/transfers", json=transfer_payload(first["id"], second["id"]))
    assert created.status_code == 201, created.text
    transfer_id = created.json()["id"]

    listed = client.get("/api/transfers").json()
    assert [row["id"] for row in listed] == [transfer_id]
    assert client.get(f"/api/transfers/{transfer_id}").json()["description"] == ""

    updated = client.put(
        f"/api/transfers/{transfer_id}",
        json={
            "booking_date": "2026-11-21",
            "amount_cents": 40000,
            "from_account_id": second["id"],
            "to_account_id": third["id"],
            "description": "Korrektur",
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["from_account_name"] == "Sparkonto"
    assert updated.json()["to_account_name"] == "Bargeld"
    assert updated.json()["amount_cents"] == 40000

    booking = legs(client, transfer_id)
    assert len(booking) == 2
    assert sorted((row["account_id"], row["amount_cents"]) for row in booking) == [
        (second["id"], -40000),
        (third["id"], 40000),
    ]
    assert all(row["booking_date"] == "2026-11-21" for row in booking)

    assert client.delete(f"/api/transfers/{transfer_id}").status_code == 204
    assert client.get(f"/api/transfers/{transfer_id}").status_code == 404
    assert client.get("/api/transfers").json() == []
    assert legs(client, transfer_id) == []


def test_ungueltige_umbuchungen_werden_abgelehnt(client: TestClient) -> None:
    account = create_account(client, "Giro")
    other = create_account(client, "Sparkonto")

    responses = [
        client.post("/api/transfers", json=transfer_payload(account["id"], account["id"])),
        client.post("/api/transfers", json=transfer_payload(account["id"], 999)),
        client.post("/api/transfers", json=transfer_payload(999, other["id"])),
        client.post(
            "/api/transfers", json=transfer_payload(account["id"], other["id"], amount_cents=0)
        ),
        client.post(
            "/api/transfers", json=transfer_payload(account["id"], other["id"], amount_cents=-100)
        ),
        client.post(
            "/api/transfers",
            json=transfer_payload(account["id"], other["id"], booking_date="20.11.2026"),
        ),
        client.post("/api/transfers", json={"from_account_id": account["id"]}),
        client.get("/api/transfers/abc"),
        client.get("/api/transfers/999"),
        client.put("/api/transfers/999", json=transfer_payload(account["id"], other["id"])),
        client.delete("/api/transfers/999"),
    ]
    assert [response.status_code for response in responses] == [
        400,
        400,
        400,
        400,
        400,
        400,
        400,
        400,
        404,
        404,
        404,
    ]


def test_umbuchung_zaehlt_nicht_als_ausgabe(client: TestClient) -> None:
    source = create_account(client, "Giro", 100000)
    target = create_account(client, "Sparkonto")
    category = client.post("/api/categories", json={"name": "Wohnen", "type": "expense"}).json()
    period = current_period()
    booked_on = date.today().replace(day=15).isoformat()

    assert (
        client.post(
            "/api/budgets",
            json={"category_id": category["id"], "period": period, "limit_cents": 100000},
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/transactions",
            json={
                "account_id": source["id"],
                "booking_date": booked_on,
                "amount_cents": -5000,
                "category_id": category["id"],
            },
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/transfers",
            json=transfer_payload(source["id"], target["id"], booking_date=booked_on),
        ).status_code
        == 201
    )

    assert dashboard_data()["month_spend_cents"] == 5000

    month = monthly_comparison(count=1, end_period=period)[-1]
    assert month["expense_cents"] == 5000
    assert month["income_cents"] == 0
    assert month["net_cents"] == -5000

    assert category_breakdown(period)[0]["total_cents"] == 5000
    assert budget_progress(period)[0]["spent_cents"] == 5000

    # Der Saldo-Verlauf enthält beide Beine: 1000 - 50 - 250 = 700 und 250.
    history = balance_history(count=1, end_period=period)[-1]
    assert history["total_cents"] == 95000
    by_account = {item["name"]: item["balance_cents"] for item in history["accounts"]}
    assert by_account == {"Giro": 70000, "Sparkonto": 25000}

    dashboard = client.get("/").text
    assert "950,00 EUR" in dashboard  # Gesamtsaldo: 1000 - 50 (transferNetto = 0)
    assert "700,00 EUR" in dashboard  # Giro: 1000 - 50 - 250
    assert "250,00 EUR" in dashboard  # Sparkonto


def test_transaction_endpunkte_schuetzen_umbuchungsbuchungen(client: TestClient) -> None:
    source = create_account(client, "Giro")
    target = create_account(client, "Sparkonto")
    created = client.post("/api/transfers", json=transfer_payload(source["id"], target["id"]))
    transfer_id = created.json()["id"]
    outgoing = next(row for row in legs(client, transfer_id) if row["amount_cents"] < 0)

    assert (
        client.put(f"/api/transactions/{outgoing['id']}", json={"amount_cents": 1}).status_code
        == 409
    )
    assert client.delete(f"/api/transactions/{outgoing['id']}").status_code == 409
    assert len(legs(client, transfer_id)) == 2

    page = client.get(f"/ui/transactions/{outgoing['id']}/edit", follow_redirects=False)
    assert page.status_code == 303
    assert page.headers["location"] == f"/ui/transfers/{transfer_id}/edit"

    assert client.post(f"/ui/transactions/{outgoing['id']}/delete").status_code == 409
    assert len(legs(client, transfer_id)) == 2


def test_konto_mit_umbuchung_kann_nicht_geloescht_werden(client: TestClient) -> None:
    source = create_account(client, "Giro")
    target = create_account(client, "Sparkonto")
    assert (
        client.post("/api/transfers", json=transfer_payload(source["id"], target["id"])).status_code
        == 201
    )

    response = client.delete(f"/api/accounts/{source['id']}")
    assert response.status_code == 409
    assert "Umbuchungen" in response.text


def test_umbuchungen_ueber_ui(client: TestClient) -> None:
    create_account(client, "Giro", 100000)
    create_account(client, "Sparkonto")

    page = client.get("/ui/transfers")
    assert "Noch keine Umbuchungen vorhanden" in page.text
    assert 'class="active" aria-current="page">Umbuchungen</a>' in page.text

    response = client.post(
        "/ui/transfers",
        data={
            "booking_date": "2026-11-20",
            "from_account_id": "1",
            "to_account_id": "2",
            "amount": "50,00",
            "description": "Dauerauftrag",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    page = client.get("/ui/transfers")
    assert "Giro" in page.text
    assert "Sparkonto" in page.text
    assert "50,00 EUR" in page.text
    assert "Dauerauftrag" in page.text

    edit_page = client.get("/ui/transfers/1/edit")
    assert edit_page.status_code == 200
    assert 'value="50,00"' in edit_page.text

    response = client.post(
        "/ui/transfers/1",
        data={
            "booking_date": "2026-11-21",
            "from_account_id": "1",
            "to_account_id": "2",
            "amount": "60,00",
            "description": "Erhöht",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    assert "60,00 EUR" in client.get("/ui/transfers").text
    assert "Umbuchung" in client.get("/ui/transactions").text

    response = client.post("/ui/transfers/1/delete", follow_redirects=False)
    assert response.status_code == 303
    assert "Noch keine Umbuchungen vorhanden" in client.get("/ui/transfers").text
    assert client.get("/api/transactions").json() == []


def test_migration_erhaelt_bestehende_daten(db_path: Path) -> None:
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
        assert "transfers" in tables
        assert "salary_rules" in tables
        row = connection.execute("SELECT * FROM transactions WHERE id = 1").fetchone()
        assert row["amount_cents"] == -123
        assert row["transfer_id"] is None
