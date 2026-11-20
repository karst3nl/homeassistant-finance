"""Tests für wiederkehrende Umbuchungen in den Fixkostenregeln."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import recurring
from db import connect, init_db
from main import app
from starlette.testclient import TestClient

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "addons" / "finance" / "app" / "migrations"
MIGRATION_001 = MIGRATIONS_DIR / "001_initial.sql"
MIGRATION_002 = MIGRATIONS_DIR / "002_recurring.sql"


def create_account(client: TestClient, name: str, initial_cents: int = 0) -> dict:
    response = client.post(
        "/api/accounts",
        json={
            "name": name,
            "type": "checking",
            "initial_balance_cents": initial_cents,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def transfer_payload(from_id: int, to_id: int, **extra: object) -> dict:
    return {
        "name": "Sparrate",
        "amount_cents": 5000,
        "direction": "transfer",
        "interval": "monthly",
        "account_id": from_id,
        "to_account_id": to_id,
        "start_date": date.today().replace(day=1).isoformat(),
        "description": "Monatlich sparen",
        **extra,
    }


def test_umbuchungsregel_erzeugt_konsistentes_buchungspaar(client: TestClient) -> None:
    source = create_account(client, "Giro", 10000)
    target = create_account(client, "Sparkonto", 20000)

    created = client.post("/api/recurring", json=transfer_payload(source["id"], target["id"]))
    assert created.status_code == 201, created.text
    rule = created.json()
    assert rule["direction"] == "transfer"
    assert rule["to_account_id"] == target["id"]
    assert rule["account_name"] == "Giro"
    assert rule["to_account_name"] == "Sparkonto"
    assert rule["category_id"] is None

    bookings = client.get("/api/transactions").json()
    assert len(bookings) == 2
    assert {booking["account_id"] for booking in bookings} == {source["id"], target["id"]}
    assert sorted(booking["amount_cents"] for booking in bookings) == [-5000, 5000]
    assert all(booking["source"] == "transfer" for booking in bookings)
    assert all(booking["transfer_id"] == bookings[0]["transfer_id"] for booking in bookings)
    assert all(booking["category_id"] is None for booking in bookings)
    assert all(booking["description"] == "Monatlich sparen" for booking in bookings)

    transfers = client.get("/api/transfers").json()
    assert len(transfers) == 1
    assert transfers[0]["from_account_id"] == source["id"]
    assert transfers[0]["to_account_id"] == target["id"]
    assert transfers[0]["recurring_rule_id"] == rule["id"]
    assert transfers[0]["recurring_period"] == date.today().strftime("%Y-%m")

    # Eine Umbuchung verändert den Gesamtsaldo nicht und zählt nicht als
    # Einnahme/Ausgabe.
    monthly = client.get("/api/stats/monthly?months=1").json()
    assert monthly[-1]["income_cents"] == 0
    assert monthly[-1]["expense_cents"] == 0
    assert client.get("/api/stats/categories?type=income").json() == []
    assert client.get("/api/stats/categories?type=expense").json() == []

    assert recurring.planned_summary()["transfer_cents"] == 5000
    assert recurring.generate_due() == 0
    assert len(client.get("/api/transfers").json()) == 1


def test_umbuchungsregel_wird_nur_einmal_pro_monat_gebucht(
    client: TestClient, db_path: Path
) -> None:
    source = create_account(client, "Giro")
    target = create_account(client, "Sparkonto")
    rule_id = recurring.create_rule(
        transfer_payload(source["id"], target["id"], start_date="2026-08-01")
    )

    assert recurring.generate_due(date(2026, 11, 20)) == 8
    assert recurring.generate_due(date(2026, 11, 20)) == 0

    with connect(db_path) as connection:
        periods = [
            row["recurring_period"]
            for row in connection.execute(
                "SELECT recurring_period FROM transfers ORDER BY booking_date"
            )
        ]
        assert periods == ["2026-08", "2026-09", "2026-10", "2026-11"]
        assert connection.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 8

        rule = connection.execute(
            "SELECT next_due FROM recurring_rules WHERE id = ?", (rule_id,)
        ).fetchone()
        assert rule["next_due"] == "2026-12-01"

    monthly = client.get("/api/stats/monthly?months=1&end_period=2026-10").json()
    assert monthly[-1]["income_cents"] == 0
    assert monthly[-1]["expense_cents"] == 0


def test_pausierte_umbuchungsregel_bucht_nichts(client: TestClient, db_path: Path) -> None:
    source = create_account(client, "Giro")
    target = create_account(client, "Sparkonto")
    rule_id = recurring.create_rule(
        transfer_payload(source["id"], target["id"], start_date="2026-08-01", active=0)
    )

    assert recurring.generate_due(date(2026, 11, 20)) == 0
    with connect(db_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM transfers").fetchone()[0] == 0
        next_due = connection.execute(
            "SELECT next_due FROM recurring_rules WHERE id = ?", (rule_id,)
        ).fetchone()[0]
        assert next_due == "2026-12-01"
    assert recurring.planned_summary()["transfer_cents"] == 0


def test_umbuchungsregel_wird_validiert(client: TestClient) -> None:
    source = create_account(client, "Giro")
    target = create_account(client, "Sparkonto")
    category = client.post("/api/categories", json={"name": "Wohnen", "type": "expense"}).json()
    valid = transfer_payload(source["id"], target["id"])

    invalid = (
        {k: v for k, v in valid.items() if k != "to_account_id"},
        {**valid, "to_account_id": source["id"]},
        {**valid, "to_account_id": 999},
        {**valid, "amount_cents": 0},
        {**valid, "direction": "unknown"},
    )
    for payload in invalid:
        response = client.post("/api/recurring", json=payload)
        assert response.status_code == 400, (payload, response.text)

    assert client.get("/api/transactions").json() == []

    # Eine versehentlich übermittelte Kategorie wird bei Umbuchungen ignoriert.
    ignored = client.post("/api/recurring", json={**valid, "category_id": category["id"]})
    assert ignored.status_code == 201, ignored.text
    assert ignored.json()["category_id"] is None


def test_umbuchungsregel_ueber_ui(client: TestClient) -> None:
    source = create_account(client, "Giro")
    target = create_account(client, "Sparkonto")

    page = client.get("/ui/recurring").text
    assert '<option value="transfer"' in page
    assert 'name="to_account_id"' in page

    form = {
        "name": "Sparrate",
        "direction": "transfer",
        "interval": "monthly",
        "amount": "50,00",
        "account_id": str(source["id"]),
        "to_account_id": str(target["id"]),
        "start_date": date.today().replace(day=1).isoformat(),
        "counterparty": "",
        "description": "Monatlich sparen",
        "active": "1",
    }
    created = client.post("/ui/recurring", data=form, follow_redirects=False)
    assert created.status_code == 303, created.text

    page = client.get("/ui/recurring").text
    assert "Umbuchung" in page
    assert "Giro → Sparkonto" in page
    assert "50,00 EUR" in page

    edit = client.get("/ui/recurring/1/edit").text
    assert 'name="to_account_id"' in edit
    assert 'value="2" selected' in edit

    updated = client.post(
        "/ui/recurring/1", data={**form, "amount": "75,00"}, follow_redirects=False
    )
    assert updated.status_code == 303
    assert "75,00 EUR" in client.get("/ui/recurring").text

    deleted = client.post("/ui/recurring/1/delete", follow_redirects=False)
    assert deleted.status_code == 303
    assert "Noch keine Regeln vorhanden." in client.get("/ui/recurring").text
    # Bereits erzeugte Umbuchungen bleiben nach dem Löschen der Regel erhalten.
    assert len(client.get("/api/transfers").json()) == 1


def test_migration_erhaelt_bestehende_regeln_und_umbuchungen(db_path: Path) -> None:
    connection = connect(db_path)
    connection.executescript(MIGRATION_001.read_text(encoding="utf-8"))
    connection.executescript(MIGRATION_002.read_text(encoding="utf-8"))
    connection.execute("INSERT INTO accounts (name, type) VALUES ('Giro', 'checking')")
    connection.execute("INSERT INTO accounts (name, type) VALUES ('Sparkonto', 'savings')")
    connection.execute(
        """INSERT INTO recurring_rules
           (name, amount_cents, direction, interval, account_id, start_date, next_due)
           VALUES ('Miete', 90000, 'expense', 'monthly', 1, '2026-11-01', '2026-11-01')"""
    )
    connection.commit()
    connection.close()

    init_db(db_path)

    with connect(db_path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 5
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(recurring_rules)")}
        assert "to_account_id" in columns
        transfer_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(transfers)")
        }
        assert "recurring_rule_id" in transfer_columns
        assert "recurring_period" in transfer_columns
        assert connection.execute("SELECT COUNT(*) FROM recurring_rules").fetchone()[0] == 1
        assert connection.execute("SELECT name FROM recurring_rules").fetchone()[0] == "Miete"

    # Nach der Migration lassen sich wiederkehrende Umbuchungen anlegen.
    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/recurring",
            json=transfer_payload(1, 2, start_date="2026-11-01"),
        )
        assert response.status_code == 201, response.text
        assert len(test_client.get("/api/transfers").json()) == 1
