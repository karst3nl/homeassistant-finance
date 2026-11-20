"""Auswertungen über die Rohdaten.

Alle Funktionen liefern ganzzahlige Cent und Perioden im Format YYYY-MM.
Es gibt keine externen Abhängigkeiten und keine versteckte Magie: jede
Kennzahl lässt sich direkt aus den Buchungen nachrechnen.
"""

from __future__ import annotations

import calendar
import re
from datetime import date

from db import transaction

_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
PALETTE = (
    "#41bdf5",
    "#e06262",
    "#4caf7d",
    "#e0a83b",
    "#9b7bdb",
    "#5ac8c2",
    "#d97bb0",
    "#8d9eaa",
)


def current_period(today: date | None = None) -> str:
    """Aktuelles Jahr-Monat als YYYY-MM."""
    return (today or date.today()).strftime("%Y-%m")


def _parts(period: str) -> tuple[int, int]:
    try:
        year_text, month_text = period.split("-")
        year, month = int(year_text), int(month_text)
        if len(year_text) != 4 or not 1 <= month <= 12:
            raise ValueError
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"Ungültige Periode: {period!r}") from exc
    return year, month


def normalize_period(period: str) -> str:
    """Periode validieren und einheitlich formatieren."""
    year, month = _parts(period)
    return f"{year:04d}-{month:02d}"


def shift_period(period: str, months: int) -> str:
    """Periode um Monate verschieben (positiv oder negativ)."""
    year, month = _parts(period)
    index = year * 12 + month - 1 + months
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def period_bounds(period: str) -> tuple[str, str]:
    """Erster und letzter Tag einer Periode als ISO-Datum."""
    year, month = _parts(period)
    last_day = calendar.monthrange(year, month)[1]
    return f"{year:04d}-{month:02d}-01", f"{year:04d}-{month:02d}-{last_day:02d}"


def month_sequence(end_period: str, count: int) -> list[str]:
    """Die letzten `count` Perioden bis einschließlich `end_period`, aufsteigend."""
    if count < 1:
        raise ValueError("'count' muss mindestens 1 sein")
    return [shift_period(end_period, offset) for offset in range(-count + 1, 1)]


def monthly_comparison(count: int = 6, end_period: str | None = None) -> list[dict]:
    """Einnahmen, Ausgaben und Netto je Monat – auch monate ohne Buchungen."""
    end = normalize_period(end_period or current_period())
    result: list[dict] = []
    with transaction() as connection:
        for period in month_sequence(end, count):
            start, stop = period_bounds(period)
            row = connection.execute(
                """
                SELECT
                  COALESCE(SUM(CASE WHEN amount_cents > 0
                                    THEN amount_cents ELSE 0 END), 0) AS income_cents,
                  COALESCE(SUM(CASE WHEN amount_cents < 0
                                    THEN -amount_cents ELSE 0 END), 0) AS expense_cents
                FROM transactions
                WHERE booking_date BETWEEN ? AND ? AND source <> 'transfer'
                """,
                (start, stop),
            ).fetchone()
            income, expense = row["income_cents"], row["expense_cents"]
            result.append(
                {
                    "period": period,
                    "income_cents": income,
                    "expense_cents": expense,
                    "net_cents": income - expense,
                }
            )
    return result


def category_breakdown(period: str | None = None, kind: str = "expense") -> list[dict]:
    """Summen je Kategorie für einen Monat, absteigend sortiert."""
    if kind not in ("expense", "income"):
        raise ValueError("'kind' muss 'expense' oder 'income' sein")
    month = normalize_period(period or current_period())
    start, stop = period_bounds(month)
    comparison = "< 0" if kind == "expense" else "> 0"

    with transaction() as connection:
        rows = connection.execute(
            f"""
            SELECT c.id, COALESCE(c.name, 'Ohne Kategorie') AS name, c.color,
                   SUM(ABS(t.amount_cents)) AS total_cents,
                   COUNT(*) AS count
            FROM transactions t
            LEFT JOIN categories c ON c.id = t.category_id
            WHERE t.booking_date BETWEEN ? AND ? AND t.amount_cents {comparison}
              AND t.source <> 'transfer'
            GROUP BY c.id
            ORDER BY total_cents DESC, name COLLATE NOCASE
            """,
            (start, stop),
        ).fetchall()

    items = [dict(row) for row in rows]
    total = sum(item["total_cents"] for item in items)
    for index, item in enumerate(items):
        item["share"] = round(item["total_cents"] / total * 100) if total else 0
        color = item["color"]
        item["color"] = (
            color if color and _COLOR_RE.fullmatch(color) else PALETTE[index % len(PALETTE)]
        )
    return items


def budget_progress(period: str | None = None) -> list[dict]:
    """Budget vs. tatsächliche Ausgaben der Kategorie im gewählten Monat.

    Ein Limit von 0 ist ein Sonderfall: jede Ausgabe gilt als überschritten.
    """
    month = normalize_period(period or current_period())
    start, stop = period_bounds(month)

    with transaction() as connection:
        rows = connection.execute(
            """
            SELECT b.id, b.category_id, b.period, b.limit_cents,
                   c.name AS category_name,
                   COALESCE(SUM(CASE WHEN t.amount_cents < 0
                                     THEN -t.amount_cents ELSE 0 END), 0) AS spent_cents
            FROM budgets b
            JOIN categories c ON c.id = b.category_id
            LEFT JOIN transactions t ON t.category_id = b.category_id
                 AND t.booking_date BETWEEN ? AND ? AND t.amount_cents < 0
                 AND t.source <> 'transfer'
            WHERE b.period = ?
            GROUP BY b.id
            ORDER BY c.name COLLATE NOCASE
            """,
            (start, stop, month),
        ).fetchall()

    result: list[dict] = []
    for row in rows:
        item = dict(row)
        limit, spent = item["limit_cents"], item["spent_cents"]
        item["remaining_cents"] = limit - spent
        item["percent"] = round(spent / limit * 100) if limit else (100 if spent else 0)
        item["state"] = (
            "over" if spent > limit else "warn" if limit and item["percent"] >= 80 else "ok"
        )
        item["bar_percent"] = min(100, max(0, item["percent"]))
        result.append(item)
    return result


def balance_history(count: int = 6, end_period: str | None = None) -> list[dict]:
    """Kontostände zum Monatsende – Anfangssaldo plus alle Buchungen bis dahin."""
    end = normalize_period(end_period or current_period())
    result: list[dict] = []
    with transaction() as connection:
        accounts = [
            dict(row)
            for row in connection.execute(
                "SELECT id, name, initial_balance_cents FROM accounts "
                "WHERE active = 1 ORDER BY name COLLATE NOCASE"
            )
        ]
        for period in month_sequence(end, count):
            _, stop = period_bounds(period)
            series = []
            for account in accounts:
                booked = connection.execute(
                    "SELECT COALESCE(SUM(amount_cents), 0) FROM transactions "
                    "WHERE account_id = ? AND booking_date <= ?",
                    (account["id"], stop),
                ).fetchone()[0]
                series.append(
                    {
                        "id": account["id"],
                        "name": account["name"],
                        "balance_cents": account["initial_balance_cents"] + booked,
                    }
                )
            result.append(
                {
                    "period": period,
                    "total_cents": sum(item["balance_cents"] for item in series),
                    "accounts": series,
                }
            )
    return result
