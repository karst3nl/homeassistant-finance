"""Kennzahlen für das Dashboard.

Größere Auswertungen liegen in `reports.py`; hier wird nur zusammengestellt,
was die Übersichtsseite unmittelbar braucht.
"""

from __future__ import annotations

from datetime import date

import recurring
import salary
from db import transaction
from reports import budget_progress, current_period


def free_cash_cents() -> int:
    """Geplantes frei verfügbares Geld pro Monat in Cent.

    Berechnung: aktives Monatsgehalt abzüglich geplanter Fixkosten und
    geplanter Umbuchungen. Wiederkehrende Einnahmen außer Gehalt und bereits
    gebuchte Beträge bleiben außen vor; der Wert ist ein Planungswert.
    """
    plan = recurring.planned_summary()
    return (
        salary.planned_summary()["monthly_cents"] - plan["expense_cents"] - plan["transfer_cents"]
    )


def dashboard_data() -> dict:
    """Alle Daten, die die Übersichtsseite braucht."""
    period = current_period()
    with transaction() as connection:
        accounts = [
            dict(row)
            for row in connection.execute(
                """
                SELECT a.id, a.name, a.currency, a.initial_balance_cents,
                       a.initial_balance_cents + COALESCE(SUM(t.amount_cents), 0)
                           AS balance_cents
                FROM accounts a
                LEFT JOIN transactions t ON t.account_id = a.id
                WHERE a.active = 1
                GROUP BY a.id
                ORDER BY a.name COLLATE NOCASE
                """
            )
        ]
        total_cents = sum(account["balance_cents"] for account in accounts)
        month_spend_cents = connection.execute(
            """
            SELECT COALESCE(SUM(-amount_cents), 0)
            FROM transactions
            WHERE amount_cents < 0 AND source <> 'transfer'
              AND substr(booking_date, 1, 7) = ?
            """,
            (period,),
        ).fetchone()[0]
        recent = [
            dict(row)
            for row in connection.execute(
                """
                SELECT t.id, t.booking_date, t.amount_cents, t.counterparty,
                       t.description, t.source, t.transfer_id,
                       a.name AS account_name, c.name AS category_name
                FROM transactions t
                JOIN accounts a ON a.id = t.account_id
                LEFT JOIN categories c ON c.id = t.category_id
                ORDER BY t.booking_date DESC, t.id DESC
                LIMIT 8
                """
            )
        ]
        expense_categories = [
            dict(row)
            for row in connection.execute(
                "SELECT id, name FROM categories WHERE type = 'expense' "
                "ORDER BY name COLLATE NOCASE"
            )
        ]

    return {
        "accounts": accounts,
        "total_cents": total_cents,
        "free_cash_cents": free_cash_cents(),
        "month_spend_cents": month_spend_cents,
        "recent": recent,
        "expense_categories": expense_categories,
        "budgets": budget_progress(period),
        "today": date.today().isoformat(),
    }


def filtered_transactions(filters: dict[str, str]) -> list[dict]:
    """Buchungsliste mit einfachen Filtern für die Oberfläche."""
    conditions: list[str] = []
    parameters: list[str] = []

    if filters.get("account_id", "").isdigit():
        conditions.append("t.account_id = ?")
        parameters.append(filters["account_id"])
    if filters.get("date_from"):
        conditions.append("t.booking_date >= ?")
        parameters.append(filters["date_from"])
    if filters.get("date_to"):
        conditions.append("t.booking_date <= ?")
        parameters.append(filters["date_to"])
    if filters.get("search"):
        conditions.append("(LOWER(t.counterparty) LIKE ? OR LOWER(t.description) LIKE ?)")
        term = f"%{filters['search'][:200].lower()}%"
        parameters.extend([term, term])

    where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    with transaction() as connection:
        rows = connection.execute(
            f"""
            SELECT t.id, t.booking_date, t.amount_cents, t.counterparty,
                   t.description, t.source, t.transfer_id, a.name AS account_name,
                   c.name AS category_name
            FROM transactions t
            JOIN accounts a ON a.id = t.account_id
            LEFT JOIN categories c ON c.id = t.category_id
            {where}
            ORDER BY t.booking_date DESC, t.id DESC
            LIMIT 200
            """,
            parameters,
        ).fetchall()
    return [dict(row) for row in rows]
