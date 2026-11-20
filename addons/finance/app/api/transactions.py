"""CRUD-Endpunkte für manuelle Buchungen."""

from __future__ import annotations

from db import transaction
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from validation import (
    amount_from_payload,
    bad,
    json_object,
    optional_str,
    parse_date,
    path_id,
    query_int,
    required_int,
)

_DEFAULT_LIMIT = 100
_MAX_LIMIT = 1000


def _ensure_reference(connection, table: str, value: int) -> None:
    if connection.execute(f"SELECT 1 FROM {table} WHERE id = ?", (value,)).fetchone() is None:
        raise bad(f"Es gibt kein(e/n) {table} mit der ID {value}")


def _list(request: Request) -> JSONResponse:
    query = request.query_params
    conditions: list[str] = []
    parameters: list[object] = []

    if "account_id" in query:
        conditions.append("account_id = ?")
        parameters.append(query_int(query, "account_id"))
    if "transfer_id" in query:
        conditions.append("transfer_id = ?")
        parameters.append(query_int(query, "transfer_id"))
    if "category_id" in query:
        conditions.append("category_id = ?")
        parameters.append(query_int(query, "category_id"))
    if "date_from" in query:
        conditions.append("booking_date >= ?")
        parameters.append(parse_date(query["date_from"], "date_from"))
    if "date_to" in query:
        conditions.append("booking_date <= ?")
        parameters.append(parse_date(query["date_to"], "date_to"))

    try:
        limit = int(query.get("limit", _DEFAULT_LIMIT))
        offset = int(query.get("offset", 0))
    except ValueError as exc:
        raise bad("'limit' und 'offset' müssen ganze Zahlen sein") from exc
    if not 1 <= limit <= _MAX_LIMIT or offset < 0:
        raise bad(f"'limit' muss 1 bis {_MAX_LIMIT} und 'offset' >= 0 sein")

    where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"SELECT * FROM transactions{where} ORDER BY booking_date DESC, id DESC LIMIT ? OFFSET ?"
    with transaction() as connection:
        rows = connection.execute(sql, (*parameters, limit, offset)).fetchall()
    return JSONResponse([dict(row) for row in rows])


def _get(request: Request) -> JSONResponse:
    transaction_id = path_id(request.path_params["transaction_id"])
    with transaction() as connection:
        row = connection.execute(
            "SELECT * FROM transactions WHERE id = ?", (transaction_id,)
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Buchung nicht gefunden")
    return JSONResponse(dict(row))


async def _create(request: Request) -> JSONResponse:
    payload = await json_object(request)
    account_id = required_int(payload, "account_id")
    booking_date = parse_date(payload.get("booking_date"))
    amount_cents = amount_from_payload(payload)
    counterparty = optional_str(payload, "counterparty")
    description = optional_str(payload, "description")
    category_id = payload.get("category_id")
    if category_id is not None:
        category_id = required_int(payload, "category_id")

    with transaction() as connection:
        _ensure_reference(connection, "accounts", account_id)
        if category_id is not None:
            _ensure_reference(connection, "categories", category_id)
        cursor = connection.execute(
            """INSERT INTO transactions
               (account_id, booking_date, amount_cents, counterparty, description, category_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (account_id, booking_date, amount_cents, counterparty, description, category_id),
        )
        row = connection.execute(
            "SELECT * FROM transactions WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
    return JSONResponse(dict(row), status_code=201)


async def _update(request: Request) -> JSONResponse:
    transaction_id = path_id(request.path_params["transaction_id"])
    payload = await json_object(request)
    with transaction() as connection:
        row = connection.execute(
            "SELECT * FROM transactions WHERE id = ?", (transaction_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Buchung nicht gefunden")
        if row["transfer_id"] is not None:
            raise HTTPException(
                status_code=409,
                detail="Buchung gehört zu einer Umbuchung; bitte unter /api/transfers bearbeiten",
            )

        account_id = (
            required_int(payload, "account_id") if "account_id" in payload else row["account_id"]
        )
        booking_date = (
            parse_date(payload["booking_date"])
            if "booking_date" in payload
            else row["booking_date"]
        )
        amount_cents = (
            amount_from_payload(payload)
            if "amount" in payload or "amount_cents" in payload
            else row["amount_cents"]
        )
        counterparty = (
            optional_str(payload, "counterparty")
            if "counterparty" in payload
            else row["counterparty"]
        )
        description = (
            optional_str(payload, "description") if "description" in payload else row["description"]
        )
        if "category_id" in payload:
            category_id = payload["category_id"]
            category_id = None if category_id is None else required_int(payload, "category_id")
        else:
            category_id = row["category_id"]

        _ensure_reference(connection, "accounts", account_id)
        if category_id is not None:
            _ensure_reference(connection, "categories", category_id)
        connection.execute(
            """UPDATE transactions
               SET account_id = ?, booking_date = ?, amount_cents = ?, counterparty = ?,
                   description = ?, category_id = ?,
                   updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
               WHERE id = ?""",
            (
                account_id,
                booking_date,
                amount_cents,
                counterparty,
                description,
                category_id,
                transaction_id,
            ),
        )
        updated = connection.execute(
            "SELECT * FROM transactions WHERE id = ?", (transaction_id,)
        ).fetchone()
    return JSONResponse(dict(updated))


def _delete(request: Request) -> Response:
    transaction_id = path_id(request.path_params["transaction_id"])
    with transaction() as connection:
        row = connection.execute(
            "SELECT transfer_id FROM transactions WHERE id = ?", (transaction_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Buchung nicht gefunden")
        if row["transfer_id"] is not None:
            raise HTTPException(
                status_code=409,
                detail="Buchung gehört zu einer Umbuchung; bitte unter /api/transfers löschen",
            )
        connection.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))
    return Response(status_code=204)


routes = [
    Route("/api/transactions", _list, methods=["GET"]),
    Route("/api/transactions", _create, methods=["POST"]),
    Route("/api/transactions/{transaction_id}", _get, methods=["GET"]),
    Route("/api/transactions/{transaction_id}", _update, methods=["PUT"]),
    Route("/api/transactions/{transaction_id}", _delete, methods=["DELETE"]),
]
