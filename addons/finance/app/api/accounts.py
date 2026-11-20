"""CRUD-Endpunkte für Konten."""

from __future__ import annotations

import sqlite3

from db import transaction
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from validation import bad, check_cents, json_object, path_id, required_str

ACCOUNT_TYPES = frozenset({"checking", "savings", "cash", "credit", "investment"})


def _list(request: Request) -> JSONResponse:
    with transaction() as connection:
        rows = connection.execute(
            "SELECT * FROM accounts ORDER BY active DESC, name COLLATE NOCASE"
        ).fetchall()
    return JSONResponse([dict(row) for row in rows])


def _get(request: Request) -> JSONResponse:
    account_id = path_id(request.path_params["account_id"])
    with transaction() as connection:
        row = connection.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Konto nicht gefunden")
    return JSONResponse(dict(row))


async def _create(request: Request) -> JSONResponse:
    payload = await json_object(request)
    name = required_str(payload, "name")
    account_type = required_str(payload, "type")
    if account_type not in ACCOUNT_TYPES:
        raise bad(f"'type' muss einer von {', '.join(sorted(ACCOUNT_TYPES))} sein")

    currency = required_str(payload, "currency", 8).upper() if "currency" in payload else "EUR"
    initial = check_cents(payload.get("initial_balance_cents", 0), "initial_balance_cents")
    active = bool(payload.get("active", True))

    with transaction() as connection:
        cursor = connection.execute(
            """INSERT INTO accounts (name, type, currency, initial_balance_cents, active)
               VALUES (?, ?, ?, ?, ?)""",
            (name, account_type, currency, initial, int(active)),
        )
        row = connection.execute(
            "SELECT * FROM accounts WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
    return JSONResponse(dict(row), status_code=201)


async def _update(request: Request) -> JSONResponse:
    account_id = path_id(request.path_params["account_id"])
    payload = await json_object(request)
    with transaction() as connection:
        row = connection.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Konto nicht gefunden")

        name = required_str(payload, "name") if "name" in payload else row["name"]
        account_type = required_str(payload, "type") if "type" in payload else row["type"]
        if account_type not in ACCOUNT_TYPES:
            raise bad(f"'type' muss einer von {', '.join(sorted(ACCOUNT_TYPES))} sein")
        currency = (
            required_str(payload, "currency", 8).upper()
            if "currency" in payload
            else row["currency"]
        )
        initial = check_cents(
            payload.get("initial_balance_cents", row["initial_balance_cents"]),
            "initial_balance_cents",
        )
        active = bool(payload.get("active", row["active"]))

        connection.execute(
            """UPDATE accounts
               SET name = ?, type = ?, currency = ?, initial_balance_cents = ?, active = ?
               WHERE id = ?""",
            (name, account_type, currency, initial, int(active), account_id),
        )
        updated = connection.execute(
            "SELECT * FROM accounts WHERE id = ?", (account_id,)
        ).fetchone()
    return JSONResponse(dict(updated))


def _delete(request: Request) -> Response:
    account_id = path_id(request.path_params["account_id"])
    try:
        with transaction() as connection:
            cursor = connection.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=409, detail="Konto kann nicht gelöscht werden, solange Buchungen existieren"
        ) from exc
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Konto nicht gefunden")
    return Response(status_code=204)


routes = [
    Route("/api/accounts", _list, methods=["GET"]),
    Route("/api/accounts", _create, methods=["POST"]),
    Route("/api/accounts/{account_id}", _get, methods=["GET"]),
    Route("/api/accounts/{account_id}", _update, methods=["PUT"]),
    Route("/api/accounts/{account_id}", _delete, methods=["DELETE"]),
]
