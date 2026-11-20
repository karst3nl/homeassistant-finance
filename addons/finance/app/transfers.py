"""Umbuchungen zwischen zwei Konten.

Eine Umbuchung ist ein eigener Datensatz plus genau zwei ganz normale
Buchungen: eine negative auf dem Quellkonto, eine positive auf dem Zielkonto.
Beide Buchungen tragen ``source = 'transfer'`` und bleiben damit aus
Einnahme/Ausgabe, Budgets und Kategorie-Auswertungen heraus, verändern aber
die Kontostände. ``transfer_id`` hält das Paar zusammen.
"""

from __future__ import annotations

from db import transaction

TRANSFER_SOURCE = "transfer"


class TransferError(ValueError):
    """Ungültige Umbuchung oder ungültige Konto-Referenz."""


def _account_name(connection, account_id: int) -> str:
    row = connection.execute("SELECT name FROM accounts WHERE id = ?", (account_id,)).fetchone()
    if row is None:
        raise TransferError(f"Das Konto mit der ID {account_id} existiert nicht.")
    return row["name"]


def _check_values(connection, values: dict) -> None:
    _account_name(connection, values["from_account_id"])
    _account_name(connection, values["to_account_id"])
    if values["from_account_id"] == values["to_account_id"]:
        raise TransferError("Quell- und Zielkonto müssen unterschiedlich sein.")
    if values["amount_cents"] <= 0:
        raise TransferError("Der Betrag muss größer als 0 sein.")


def _leg_labels(connection, values: dict) -> tuple[str, str]:
    """Gegenstellen für die beiden Buchungen aus den Kontonamen ableiten."""
    from_name = _account_name(connection, values["from_account_id"])
    to_name = _account_name(connection, values["to_account_id"])
    return f"nach {to_name}"[:200], f"von {from_name}"[:200]


def _insert_legs(connection, transfer_id: int, values: dict) -> None:
    outgoing, incoming = _leg_labels(connection, values)
    for account_id, amount, counterparty in (
        (values["from_account_id"], -values["amount_cents"], outgoing),
        (values["to_account_id"], values["amount_cents"], incoming),
    ):
        connection.execute(
            """INSERT INTO transactions
               (account_id, booking_date, amount_cents, counterparty, description,
                category_id, source, transfer_id)
               VALUES (?, ?, ?, ?, ?, NULL, 'transfer', ?)""",
            (
                account_id,
                values["booking_date"],
                amount,
                counterparty,
                values.get("description", ""),
                transfer_id,
            ),
        )


def _sync_legs(connection, transfer_id: int, values: dict) -> None:
    """Bestehende Buchungen aktualisieren und fehlende ergänzen."""
    rows = connection.execute(
        "SELECT id FROM transactions WHERE transfer_id = ? ORDER BY amount_cents, id",
        (transfer_id,),
    ).fetchall()

    # Zuerst lösen, damit ein Tausch der Konten nicht mit dem eindeutigen
    # Index (transfer_id, account_id) kollidiert.
    for row in rows:
        connection.execute("UPDATE transactions SET transfer_id = NULL WHERE id = ?", (row["id"],))

    for row in rows[2:]:
        connection.execute("DELETE FROM transactions WHERE id = ?", (row["id"],))

    outgoing, incoming = _leg_labels(connection, values)
    for index, (account_id, amount, counterparty) in enumerate(
        (
            (values["from_account_id"], -values["amount_cents"], outgoing),
            (values["to_account_id"], values["amount_cents"], incoming),
        )
    ):
        fields = (
            transfer_id,
            account_id,
            values["booking_date"],
            amount,
            counterparty,
            values.get("description", ""),
        )
        if index < len(rows):
            connection.execute(
                """UPDATE transactions SET
                       transfer_id = ?, account_id = ?, booking_date = ?, amount_cents = ?,
                       counterparty = ?, description = ?, category_id = NULL,
                       source = 'transfer',
                       updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                   WHERE id = ?""",
                (*fields, rows[index]["id"]),
            )
        else:
            connection.execute(
                """INSERT INTO transactions
                   (transfer_id, account_id, booking_date, amount_cents, counterparty,
                    description, category_id, source)
                   VALUES (?, ?, ?, ?, ?, ?, NULL, 'transfer')""",
                fields,
            )


def create_transfer(values: dict) -> int:
    """Umbuchung anlegen und ihre ID zurückgeben."""
    with transaction() as connection:
        _check_values(connection, values)
        cursor = connection.execute(
            """INSERT INTO transfers
               (booking_date, amount_cents, from_account_id, to_account_id, description)
               VALUES (?, ?, ?, ?, ?)""",
            (
                values["booking_date"],
                values["amount_cents"],
                values["from_account_id"],
                values["to_account_id"],
                values.get("description", ""),
            ),
        )
        transfer_id = int(cursor.lastrowid)
        _insert_legs(connection, transfer_id, values)
        return transfer_id


def update_transfer(transfer_id: int, values: dict) -> None:
    """Umbuchung und beide Buchungen aktualisieren."""
    with transaction() as connection:
        if (
            connection.execute("SELECT 1 FROM transfers WHERE id = ?", (transfer_id,)).fetchone()
            is None
        ):
            raise TransferError("Umbuchung nicht gefunden")
        _check_values(connection, values)
        connection.execute(
            """UPDATE transfers SET
                   booking_date = ?, amount_cents = ?, from_account_id = ?,
                   to_account_id = ?, description = ?,
                   updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
               WHERE id = ?""",
            (
                values["booking_date"],
                values["amount_cents"],
                values["from_account_id"],
                values["to_account_id"],
                values.get("description", ""),
                transfer_id,
            ),
        )
        _sync_legs(connection, transfer_id, values)


def delete_transfer(transfer_id: int) -> None:
    """Umbuchung samt beider Buchungen löschen."""
    with transaction() as connection:
        cursor = connection.execute("DELETE FROM transfers WHERE id = ?", (transfer_id,))
        if cursor.rowcount == 0:
            raise TransferError("Umbuchung nicht gefunden")


def get_transfer(transfer_id: int) -> dict | None:
    with transaction() as connection:
        row = connection.execute(
            """SELECT t.*, f.name AS from_account_name, to_a.name AS to_account_name,
                      r.name AS recurring_rule_name
               FROM transfers t
               JOIN accounts f ON f.id = t.from_account_id
               JOIN accounts to_a ON to_a.id = t.to_account_id
               LEFT JOIN recurring_rules r ON r.id = t.recurring_rule_id
               WHERE t.id = ?""",
            (transfer_id,),
        ).fetchone()
    return dict(row) if row is not None else None


def list_transfers() -> list[dict]:
    with transaction() as connection:
        rows = connection.execute(
            """SELECT t.*, f.name AS from_account_name, to_a.name AS to_account_name,
                      r.name AS recurring_rule_name
               FROM transfers t
               JOIN accounts f ON f.id = t.from_account_id
               JOIN accounts to_a ON to_a.id = t.to_account_id
               LEFT JOIN recurring_rules r ON r.id = t.recurring_rule_id
               ORDER BY t.booking_date DESC, t.id DESC"""
        ).fetchall()
    return [dict(row) for row in rows]
