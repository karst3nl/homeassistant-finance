"""Tests für die mobile, touchfreundliche Darstellung."""

from __future__ import annotations

import re
from pathlib import Path

from starlette.testclient import TestClient

CSS_PATH = (
    Path(__file__).resolve().parents[1] / "addons" / "finance" / "app" / "static" / "style.css"
)


def test_viewport_ist_fuer_mobil_und_safe_areas_gesetzt(client: TestClient) -> None:
    page = client.get("/")

    assert (
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />'
        in page.text
    )


def test_css_enthaelt_responsive_regeln() -> None:
    css = CSS_PATH.read_text(encoding="utf-8")

    assert "@media (max-width: 700px)" in css
    assert "@media (max-width: 640px)" in css
    assert "@media (pointer: coarse)" in css
    assert "content: attr(data-label)" in css
    assert "min-height: 44px" in css
    assert "overflow-x: auto" in css
    assert "flex-wrap: nowrap;" in css
    assert "flex: 1 1 auto;" in css
    assert "min-width: 0;" in css


def test_tabellen_haben_beschriftungen_fuer_die_kartenansicht(client: TestClient) -> None:
    account = client.post(
        "/api/accounts",
        json={"name": "Giro", "type": "checking", "initial_balance_cents": 10000},
    ).json()
    other = client.post("/api/accounts", json={"name": "Sparkonto", "type": "savings"}).json()
    category = client.post(
        "/api/categories", json={"name": "Lebensmittel", "type": "expense"}
    ).json()
    income_category = client.post(
        "/api/categories", json={"name": "Gehalt", "type": "income"}
    ).json()
    client.post(
        "/api/transactions",
        json={
            "account_id": account["id"],
            "booking_date": "2026-11-20",
            "amount_cents": -1234,
            "category_id": category["id"],
        },
    )
    client.post(
        "/api/budgets",
        json={"category_id": category["id"], "period": "2026-11", "limit_cents": 20000},
    )
    client.post(
        "/api/recurring",
        json={
            "name": "Miete",
            "amount_cents": 100000,
            "direction": "expense",
            "interval": "monthly",
            "account_id": account["id"],
            "start_date": "2026-11-01",
        },
    )
    client.post(
        "/api/transfers",
        json={
            "from_account_id": account["id"],
            "to_account_id": other["id"],
            "booking_date": "2026-11-20",
            "amount_cents": 5000,
        },
    )
    client.post(
        "/api/salary",
        json={
            "name": "Monatsgehalt",
            "amount_cents": 250000,
            "account_id": account["id"],
            "category_id": income_category["id"],
            "start_date": "2026-11-01",
        },
    )
    client.post("/ui/backups")

    paths = (
        "/",
        "/ui/transactions",
        "/ui/accounts",
        "/ui/categories",
        "/ui/budgets",
        "/ui/recurring",
        "/ui/salary",
        "/ui/transfers",
        "/ui/reports",
        "/ui/backups",
    )
    for path in paths:
        page = client.get(path)
        assert page.status_code == 200, path
        cells = re.findall(r"<td[^>]*>", page.text)
        assert cells, path
        for cell in cells:
            assert "data-label=" in cell or "actions-cell" in cell, (path, cell)
