"""Tests für Auswertungen: Perioden, Kennzahlen und Gegenproben."""

from __future__ import annotations

from pathlib import Path

import pytest
from charts import bar_chart, donut_chart, line_chart
from db import connect
from reports import (
    balance_history,
    budget_progress,
    category_breakdown,
    month_sequence,
    monthly_comparison,
    normalize_period,
    period_bounds,
    shift_period,
)
from starlette.testclient import TestClient


def create_account(client: TestClient) -> dict:
    response = client.post("/api/accounts", json={"name": "Giro", "type": "checking"})
    assert response.status_code == 201
    return response.json()


def create_category(client: TestClient, name: str) -> dict:
    response = client.post("/api/categories", json={"name": name, "type": "expense"})
    assert response.status_code == 201
    return response.json()


def add_transaction(
    client: TestClient, account_id: int, booking_date: str, amount_cents: int, category_id=None
) -> None:
    response = client.post(
        "/api/transactions",
        json={
            "account_id": account_id,
            "booking_date": booking_date,
            "amount_cents": amount_cents,
            "category_id": category_id,
        },
    )
    assert response.status_code == 201, response.text


def test_period_hilfsfunktionen() -> None:
    assert period_bounds("2024-02") == ("2024-02-01", "2024-02-29")
    assert period_bounds("2026-11") == ("2026-11-01", "2026-11-30")
    assert shift_period("2026-01", -1) == "2025-12"
    assert shift_period("2025-12", 1) == "2026-01"
    assert month_sequence("2026-01", 3) == ["2025-11", "2025-12", "2026-01"]
    assert normalize_period("2026-1") == "2026-01"

    with pytest.raises(ValueError):
        normalize_period("2026-13")
    with pytest.raises(ValueError):
        month_sequence("2026-01", 0)


def test_monatsvergleich_und_kategorien(client: TestClient) -> None:
    account = create_account(client)
    food = create_category(client, "Lebensmittel")
    salary = client.post("/api/categories", json={"name": "Gehalt", "type": "income"}).json()
    add_transaction(client, account["id"], "2026-10-05", 100000, salary["id"])
    add_transaction(client, account["id"], "2026-10-10", -20000, food["id"])
    add_transaction(client, account["id"], "2026-11-05", -1234, food["id"])
    add_transaction(client, account["id"], "2026-11-20", -3000)

    months = monthly_comparison(3, "2026-11")
    assert [month["period"] for month in months] == ["2026-09", "2026-10", "2026-11"]
    assert months[0] == {
        "period": "2026-09",
        "income_cents": 0,
        "expense_cents": 0,
        "net_cents": 0,
    }
    assert months[1]["income_cents"] == 100000
    assert months[1]["expense_cents"] == 20000
    assert months[1]["net_cents"] == 80000
    assert months[2]["expense_cents"] == 4234
    assert months[2]["net_cents"] == -4234

    expenses = category_breakdown("2026-11")
    assert [(item["name"], item["total_cents"]) for item in expenses] == [
        ("Ohne Kategorie", 3000),
        ("Lebensmittel", 1234),
    ]
    assert sum(item["share"] for item in expenses) == 100
    assert expenses[0]["color"].startswith("#")

    income = category_breakdown("2026-10", "income")
    assert [(item["name"], item["total_cents"]) for item in income] == [("Gehalt", 100000)]
    assert category_breakdown("2026-09") == []

    with pytest.raises(ValueError):
        category_breakdown("2026-11", "unknown")


def test_budget_fortschritt(client: TestClient) -> None:
    account = create_account(client)
    food = create_category(client, "Lebensmittel")
    other = create_category(client, "Mobilität")
    client.post(
        "/api/budgets",
        json={"category_id": food["id"], "period": "2026-11", "limit_cents": 20000},
    )
    client.post(
        "/api/budgets",
        json={"category_id": other["id"], "period": "2026-11", "limit_cents": 20000},
    )
    add_transaction(client, account["id"], "2026-10-31", -500, food["id"])
    add_transaction(client, account["id"], "2026-11-10", -25000, food["id"])
    add_transaction(client, account["id"], "2026-12-01", -1000, food["id"])
    add_transaction(client, account["id"], "2026-11-15", -16000, other["id"])

    budgets = {item["category_name"]: item for item in budget_progress("2026-11")}
    food_budget = budgets["Lebensmittel"]
    assert food_budget["spent_cents"] == 25000
    assert food_budget["limit_cents"] == 20000
    assert food_budget["remaining_cents"] == -5000
    assert food_budget["percent"] == 125
    assert food_budget["bar_percent"] == 100
    assert food_budget["state"] == "over"

    other_budget = budgets["Mobilität"]
    assert other_budget["spent_cents"] == 16000
    assert other_budget["percent"] == 80
    assert other_budget["state"] == "warn"
    assert budget_progress("2026-10") == []


def test_budget_mit_limit_null(client: TestClient) -> None:
    create_category(client, "Sonstiges")
    response = client.post(
        "/api/budgets", json={"category_id": 1, "period": "2026-11", "limit_cents": 0}
    )
    assert response.status_code == 201
    budget = budget_progress("2026-11")[0]
    assert budget["percent"] == 0
    assert budget["state"] == "ok"

    account = create_account(client)
    add_transaction(client, account["id"], "2026-11-02", -100, 1)
    budget = budget_progress("2026-11")[0]
    assert budget["percent"] == 100
    assert budget["state"] == "over"


def test_saldo_verlauf(client: TestClient) -> None:
    account = create_account(client)
    client.put(
        f"/api/accounts/{account['id']}",
        json={"initial_balance_cents": 100000},
    )
    add_transaction(client, account["id"], "2026-10-15", -2000)
    add_transaction(client, account["id"], "2026-11-02", 50000)
    add_transaction(client, account["id"], "2026-11-20", -1000)

    history = balance_history(2, "2026-11")
    assert [item["period"] for item in history] == ["2026-10", "2026-11"]
    assert history[0]["total_cents"] == 98000
    assert history[1]["total_cents"] == 147000
    assert history[1]["accounts"][0]["name"] == "Giro"
    assert history[1]["accounts"][0]["balance_cents"] == 147000


def test_gegenprobe_aus_rohdaten(client: TestClient, db_path: Path) -> None:
    """Jede Kennzahl muss unabhängig aus den Buchungen nachrechenbar sein."""
    account = create_account(client)
    client.put(f"/api/accounts/{account['id']}", json={"initial_balance_cents": 50000})
    food = create_category(client, "Lebensmittel")
    income = client.post("/api/categories", json={"name": "Gehalt", "type": "income"}).json()
    rows = [
        ("2026-09-30", -1000, food["id"]),
        ("2026-10-01", 200000, income["id"]),
        ("2026-10-15", -25000, food["id"]),
        ("2026-10-31", -500, None),
        ("2026-11-02", -3333, food["id"]),
        ("2026-11-28", 1000, income["id"]),
    ]
    for booking_date, amount, category_id in rows:
        add_transaction(client, account["id"], booking_date, amount, category_id)

    with connect(db_path) as connection:
        raw = connection.execute("SELECT booking_date, amount_cents FROM transactions").fetchall()

    for month in monthly_comparison(3, "2026-11"):
        in_month = [
            row["amount_cents"] for row in raw if row["booking_date"][:7] == month["period"]
        ]
        assert month["income_cents"] == sum(v for v in in_month if v > 0)
        assert month["expense_cents"] == -sum(v for v in in_month if v < 0)
        assert month["net_cents"] == sum(in_month)

    breakdown = category_breakdown("2026-10")
    assert sum(item["total_cents"] for item in breakdown) == 25500
    assert balance_history(3, "2026-11")[-1]["total_cents"] == 50000 + sum(
        row["amount_cents"] for row in raw
    )


def test_statistik_api(client: TestClient) -> None:
    account = create_account(client)
    category = create_category(client, "Lebensmittel")
    add_transaction(client, account["id"], "2026-11-05", -1234, category["id"])
    client.post(
        "/api/budgets",
        json={"category_id": category["id"], "period": "2026-11", "limit_cents": 5000},
    )

    monthly = client.get("/api/stats/monthly?months=1&end_period=2026-11").json()
    categories = client.get("/api/stats/categories?period=2026-11").json()
    budgets = client.get("/api/stats/budgets?period=2026-11").json()
    balance = client.get("/api/stats/balance?months=1&end_period=2026-11").json()

    assert monthly == monthly_comparison(1, "2026-11")
    assert categories == category_breakdown("2026-11")
    assert budgets == budget_progress("2026-11")
    assert balance == balance_history(1, "2026-11")
    assert budgets[0]["spent_cents"] == 1234

    assert client.get("/api/stats/monthly?months=0").status_code == 400
    assert client.get("/api/stats/monthly?months=abc").status_code == 400
    assert client.get("/api/stats/categories?period=2026-13").status_code == 400
    assert client.get("/api/stats/categories?type=unknown").status_code == 400


def test_svg_charts_escapen_texte(client: TestClient) -> None:
    chart = bar_chart(monthly_comparison(3, "2026-11"))
    assert "<svg" in chart and "<rect" in chart and "</svg>" in chart
    assert "Keine Daten" in bar_chart([])

    create_category(client, "<script>alert(1)</script>")
    account = create_account(client)
    add_transaction(client, account["id"], "2026-11-05", -100, 1)
    items = category_breakdown("2026-11")
    donut = donut_chart(items)
    assert "<svg" in donut and "stroke-dasharray" in donut
    assert "<script>" not in donut
    assert "&lt;script&gt;" in donut
    assert "<svg" in line_chart(balance_history(3, "2026-11"))
    assert "Keine Daten" in line_chart([])
