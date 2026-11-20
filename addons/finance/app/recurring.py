"""Wiederkehrende Buchungen: Regeln verwalten und fällige Buchungen erzeugen.

Eine Regel beschreibt nur, was wann gebucht werden soll. Die erzeugten Buchungen
sind ganz normale Zeilen in ``transactions`` und damit in allen Auswertungen
sichtbar. ``recurring_rule_id`` + ``recurring_period`` verhindern Duplikate.
"""

from __future__ import annotations

import calendar
from datetime import date

from db import transaction

INTERVALS = ("monthly", "yearly")
DIRECTIONS = ("expense", "income")

# Schutz vor Unsinn wie "Startdatum 1900": pro Lauf und Regel höchstens so viele
# Fälligkeiten erzeugen. Die restlichen holt der nächste Lauf nach.
MAX_OCCURRENCES = 120


class RecurringError(ValueError):
    """Ungültige Regel oder ungültige Referenz."""


def add_months(value: date, months: int) -> date:
    """Monate addieren und den Tag auf die Monatslänge begrenzen."""
    index = value.month - 1 + months
    year, month = value.year + index // 12, index % 12 + 1
    return date(year, month, min(value.day, calendar.monthrange(year, month)[1]))


def next_due_date(value: date, interval: str) -> date:
    """Nächsten Fälligkeitstermin einer Regel berechnen."""
    if interval not in INTERVALS:
        raise RecurringError(f"Unbekanntes Intervall: {interval}")
    return add_months(value, 1 if interval == "monthly" else 12)


def _check_references(connection, values: dict) -> None:
    account = connection.execute(
        "SELECT 1 FROM accounts WHERE id = ?", (values["account_id"],)
    ).fetchone()
    if account is None:
        raise RecurringError("Das gewählte Konto existiert nicht.")
    category_id = values.get("category_id")
    if category_id is not None:
        row = connection.execute(
            "SELECT type FROM categories WHERE id = ?", (category_id,)
        ).fetchone()
        if row is None:
            raise RecurringError("Die gewählte Kategorie existiert nicht.")
        if row["type"] != values["direction"]:
            raise RecurringError("Die Kategorie passt nicht zur Art der Regel.")


def create_rule(values: dict) -> int:
    """Regel anlegen und ihre ID zurückgeben."""
    with transaction() as connection:
        _check_references(connection, values)
        cursor = connection.execute(
            """INSERT INTO recurring_rules
               (name, amount_cents, direction, interval, account_id, category_id,
                start_date, next_due, counterparty, description, active)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                values["name"],
                values["amount_cents"],
                values["direction"],
                values["interval"],
                values["account_id"],
                values.get("category_id"),
                values["start_date"],
                values["start_date"],
                values.get("counterparty", ""),
                values.get("description", ""),
                int(values.get("active", 1)),
            ),
        )
        return int(cursor.lastrowid)


def update_rule(rule_id: int, values: dict) -> None:
    """Regel aktualisieren. Bei geändertem Startdatum wird die Folge neu berechnet."""
    with transaction() as connection:
        old = connection.execute(
            "SELECT * FROM recurring_rules WHERE id = ?", (rule_id,)
        ).fetchone()
        if old is None:
            raise RecurringError("Regel nicht gefunden")
        _check_references(connection, values)
        next_due = (
            values["start_date"] if values["start_date"] != old["start_date"] else old["next_due"]
        )
        connection.execute(
            """UPDATE recurring_rules SET
                   name = ?, amount_cents = ?, direction = ?, interval = ?,
                   account_id = ?, category_id = ?, start_date = ?, next_due = ?,
                   counterparty = ?, description = ?, active = ?,
                   updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
               WHERE id = ?""",
            (
                values["name"],
                values["amount_cents"],
                values["direction"],
                values["interval"],
                values["account_id"],
                values.get("category_id"),
                values["start_date"],
                next_due,
                values.get("counterparty", ""),
                values.get("description", ""),
                int(values.get("active", 1)),
                rule_id,
            ),
        )


def delete_rule(rule_id: int) -> None:
    """Regel löschen; bereits erzeugte Buchungen bleiben erhalten."""
    with transaction() as connection:
        cursor = connection.execute("DELETE FROM recurring_rules WHERE id = ?", (rule_id,))
        if cursor.rowcount == 0:
            raise RecurringError("Regel nicht gefunden")


def get_rule(rule_id: int) -> dict | None:
    with transaction() as connection:
        row = connection.execute(
            """SELECT r.*, a.name AS account_name, c.name AS category_name
               FROM recurring_rules r
               JOIN accounts a ON a.id = r.account_id
               LEFT JOIN categories c ON c.id = r.category_id
               WHERE r.id = ?""",
            (rule_id,),
        ).fetchone()
    return dict(row) if row is not None else None


def list_rules() -> list[dict]:
    with transaction() as connection:
        rows = connection.execute(
            """SELECT r.*, a.name AS account_name, c.name AS category_name
               FROM recurring_rules r
               JOIN accounts a ON a.id = r.account_id
               LEFT JOIN categories c ON c.id = r.category_id
               ORDER BY r.next_due, r.name COLLATE NOCASE"""
        ).fetchall()
    return [dict(row) for row in rows]


def planned_summary() -> dict:
    """Geplante Einnahmen und Ausgaben pro Monat (Jahresbeträge durch 12)."""
    monthly_share = (
        "CASE WHEN interval = 'monthly' THEN amount_cents ELSE (amount_cents + 6) / 12 END"
    )
    with transaction() as connection:
        row = connection.execute(
            f"""
            SELECT
              COALESCE(SUM(CASE WHEN active = 1 AND direction = 'expense'
                                THEN {monthly_share} ELSE 0 END), 0) AS expense_cents,
              COALESCE(SUM(CASE WHEN active = 1 AND direction = 'income'
                                THEN {monthly_share} ELSE 0 END), 0) AS income_cents,
              COUNT(*) AS rule_count
            FROM recurring_rules
            """
        ).fetchone()
    return dict(row)


def _generate_due(connection, today: date) -> int:
    rows = connection.execute(
        "SELECT * FROM recurring_rules WHERE next_due <= ? ORDER BY next_due, id",
        (today.isoformat(),),
    ).fetchall()

    created = 0
    for rule in rows:
        due = date.fromisoformat(rule["next_due"])
        cents = rule["amount_cents"]
        amount = -cents if rule["direction"] == "expense" else cents
        count = 0
        while due <= today and count < MAX_OCCURRENCES:
            if rule["active"]:
                period = (
                    due.strftime("%Y-%m") if rule["interval"] == "monthly" else f"{due.year:04d}"
                )
                cursor = connection.execute(
                    """INSERT OR IGNORE INTO transactions
                       (account_id, booking_date, amount_cents, counterparty, description,
                        category_id, source, recurring_rule_id, recurring_period)
                       VALUES (?, ?, ?, ?, ?, ?, 'recurring', ?, ?)""",
                    (
                        rule["account_id"],
                        due.isoformat(),
                        amount,
                        rule["counterparty"],
                        rule["description"],
                        rule["category_id"],
                        rule["id"],
                        period,
                    ),
                )
                created += cursor.rowcount
            due = next_due_date(due, rule["interval"])
            count += 1
        # Auch pausierte Regeln rücken weiter, damit Reaktivierung nicht nachbucht.
        connection.execute(
            "UPDATE recurring_rules SET next_due = ? WHERE id = ?", (due.isoformat(), rule["id"])
        )
    return created


def generate_due(today: date | None = None) -> int:
    """Alle bis heute fälligen Buchungen anlegen; Anzahl neuer Buchungen."""
    with transaction() as connection:
        return _generate_due(connection, today or date.today())
