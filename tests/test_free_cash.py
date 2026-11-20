"""Tests für die Kennzahl „frei verfügbares Geld“ auf der Übersicht."""

from __future__ import annotations

from datetime import date

import recurring
import salary
from starlette.testclient import TestClient
from stats import dashboard_data


def create_account(client: TestClient, name: str) -> dict:
    response = client.post(
        "/api/accounts",
        json={"name": name, "type": "checking", "initial_balance_cents": 0},
    )
    assert response.status_code == 201, response.text
    return response.json()


def start_date() -> str:
    return date.today().replace(day=1).isoformat()


def recurring_rule(
    name: str,
    amount_cents: int,
    direction: str,
    account_id: int,
    *,
    to_account_id: int | None = None,
    interval: str = "monthly",
) -> dict:
    return {
        "name": name,
        "amount_cents": amount_cents,
        "direction": direction,
        "interval": interval,
        "account_id": account_id,
        "to_account_id": to_account_id,
        "start_date": start_date(),
    }


def test_frei_verfuegbares_geld_beruecksichtigt_alle_plangroessen(client: TestClient) -> None:
    giro = create_account(client, "Giro")
    savings = create_account(client, "Sparkonto")

    salary.create_rule(
        {
            "name": "Monatsgehalt",
            "amount_cents": 250000,
            "account_id": giro["id"],
            "start_date": start_date(),
        }
    )
    salary.create_rule(
        {
            "name": "Pausiertes Gehalt",
            "amount_cents": 100000,
            "account_id": giro["id"],
            "start_date": start_date(),
            "active": 0,
        }
    )

    recurring.create_rule(recurring_rule("Miete", 90000, "expense", giro["id"]))
    recurring.create_rule(
        recurring_rule("Versicherung", 120000, "expense", giro["id"], interval="yearly")
    )
    recurring.create_rule(recurring_rule("Zinsen", 50000, "income", giro["id"]))
    recurring.create_rule(
        recurring_rule("Sparrate", 30000, "transfer", giro["id"], to_account_id=savings["id"])
    )

    # 2500 Gehalt - 900 Miete - 100 Versicherung/Monat - 300 Sparrate = 1200.
    # Pausiertes Gehalt und wiederkehrende Zinsen zählen nicht mit.
    assert dashboard_data()["free_cash_cents"] == 120000


def test_frei_verfuegbares_geld_ohne_regeln_ist_null(client: TestClient) -> None:
    assert dashboard_data()["free_cash_cents"] == 0


def test_dashboard_zeigt_frei_verfuegbares_geld_oben(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200

    text = response.text
    assert "Frei verfügbares Geld" in text
    assert "Gehalt − Fixkosten − geplante Umbuchungen" in text
    assert text.index("Frei verfügbares Geld") < text.index("Saldo gesamt")
    assert text.index("Saldo gesamt") < text.index("Ausgaben diesen Monat")


def test_negatives_frei_verfuegbares_geld_wird_gekennzeichnet(client: TestClient) -> None:
    account = create_account(client, "Giro")
    salary.create_rule(
        {
            "name": "Monatsgehalt",
            "amount_cents": 10000,
            "account_id": account["id"],
            "start_date": start_date(),
        }
    )
    recurring.create_rule(recurring_rule("Miete", 20000, "expense", account["id"]))

    page = client.get("/").text
    assert 'class="value negative"' in page
    assert "-100,00 EUR" in page
