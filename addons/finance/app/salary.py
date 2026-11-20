"""Monatsgehalt: eigene Regeln und automatische monatliche Einnahmen.

Das Gehalt ist bewusst nicht Teil der Fixkosten. Die erzeugten Buchungen sind
aber ganz normale Zeilen in ``transactions`` und erscheinen daher in Saldo,
Einnahmen und Auswertungen. ``salary_rule_id`` + ``salary_period`` sorgen
dafür, dass ein Monat nicht doppelt gebucht wird.
"""

from __future__ import annotations

from datetime import date

from db import transaction
from recurring import add_months

MAX_OCCURRENCES = 120


class SalaryError(ValueError):
    """Ungültige Gehaltsregel oder ungültige Referenz."""


def _check_references(connection, values: dict) -> None:
    account = connection.execute(
        "SELECT 1 FROM accounts WHERE id = ?", (values["account_id"],)
    ).fetchone()
    if account is None:
        raise SalaryError("Das gewählte Konto existiert nicht.")
    category_id = values.get("category_id")
    if category_id is not None:
        row = connection.execute(
            "SELECT type FROM categories WHERE id = ?", (category_id,)
        ).fetchone()
        if row is None:
            raise SalaryError("Die gewählte Kategorie existiert nicht.")
        if row["type"] != "income":
            raise SalaryError("Die Kategorie muss eine Einnahme-Kategorie sein.")


def create_rule(values: dict) -> int:
    """Gehaltsregel anlegen und ihre ID zurückgeben."""
    with transaction() as connection:
        _check_references(connection, values)
        cursor = connection.execute(
            """INSERT INTO salary_rules
               (name, amount_cents, account_id, category_id, start_date, next_due,
                counterparty, description, active)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                values["name"],
                values["amount_cents"],
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
    """Regel aktualisieren. Bei neuem Startdatum wird die Folge neu berechnet."""
    with transaction() as connection:
        old = connection.execute("SELECT * FROM salary_rules WHERE id = ?", (rule_id,)).fetchone()
        if old is None:
            raise SalaryError("Gehaltsregel nicht gefunden")
        _check_references(connection, values)
        next_due = (
            values["start_date"] if values["start_date"] != old["start_date"] else old["next_due"]
        )
        connection.execute(
            """UPDATE salary_rules SET
                   name = ?, amount_cents = ?, account_id = ?, category_id = ?,
                   start_date = ?, next_due = ?, counterparty = ?, description = ?,
                   active = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
               WHERE id = ?""",
            (
                values["name"],
                values["amount_cents"],
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
        cursor = connection.execute("DELETE FROM salary_rules WHERE id = ?", (rule_id,))
        if cursor.rowcount == 0:
            raise SalaryError("Gehaltsregel nicht gefunden")


def get_rule(rule_id: int) -> dict | None:
    with transaction() as connection:
        row = connection.execute(
            """SELECT s.*, a.name AS account_name, c.name AS category_name
               FROM salary_rules s
               JOIN accounts a ON a.id = s.account_id
               LEFT JOIN categories c ON c.id = s.category_id
               WHERE s.id = ?""",
            (rule_id,),
        ).fetchone()
    return dict(row) if row is not None else None


def list_rules() -> list[dict]:
    with transaction() as connection:
        rows = connection.execute(
            """SELECT s.*, a.name AS account_name, c.name AS category_name
               FROM salary_rules s
               JOIN accounts a ON a.id = s.account_id
               LEFT JOIN categories c ON c.id = s.category_id
               ORDER BY s.next_due, s.name COLLATE NOCASE"""
        ).fetchall()
    return [dict(row) for row in rows]


def planned_summary() -> dict:
    """Geplantes Monatsgehalt und Anzahl der Regeln."""
    with transaction() as connection:
        row = connection.execute(
            """SELECT
                 COALESCE(SUM(CASE WHEN active = 1 THEN amount_cents ELSE 0 END), 0)
                     AS monthly_cents,
                 COUNT(*) AS rule_count,
                 MIN(CASE WHEN active = 1 THEN next_due END) AS next_due
               FROM salary_rules"""
        ).fetchone()
    return dict(row)


def _generate_due(connection, today: date) -> int:
    rows = connection.execute(
        "SELECT * FROM salary_rules WHERE next_due <= ? ORDER BY next_due, id",
        (today.isoformat(),),
    ).fetchall()

    created = 0
    for rule in rows:
        due = date.fromisoformat(rule["next_due"])
        count = 0
        while due <= today and count < MAX_OCCURRENCES:
            if rule["active"]:
                period = due.strftime("%Y-%m")
                cursor = connection.execute(
                    """INSERT OR IGNORE INTO transactions
                       (account_id, booking_date, amount_cents, counterparty, description,
                        category_id, source, salary_rule_id, salary_period)
                       VALUES (?, ?, ?, ?, ?, ?, 'salary', ?, ?)""",
                    (
                        rule["account_id"],
                        due.isoformat(),
                        rule["amount_cents"],
                        rule["counterparty"],
                        rule["description"],
                        rule["category_id"],
                        rule["id"],
                        period,
                    ),
                )
                created += cursor.rowcount
            due = add_months(due, 1)
            count += 1
        # Auch pausierte Regeln rücken weiter, damit Reaktivierung nicht nachbucht.
        connection.execute(
            "UPDATE salary_rules SET next_due = ? WHERE id = ?", (due.isoformat(), rule["id"])
        )
    return created


def generate_due(today: date | None = None) -> int:
    """Alle bis heute fälligen Gehälter buchen; Anzahl neuer Buchungen."""
    with transaction() as connection:
        return _generate_due(connection, today or date.today())
