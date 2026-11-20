"""CRUD-Endpunkte für Budgets pro Kategorie und Monat."""

from __future__ import annotations

import sqlite3

from db import transaction
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from validation import bad, check_cents, json_object, parse_period, path_id, required_int


def _list(request: Request) -> JSONResponse:
    period = request.query_params.get("period")
    with transaction() as connection:
        if period:
            sql = """SELECT budgets.*, categories.name AS category_name
                     FROM budgets JOIN categories ON categories.id = budgets.category_id
                     WHERE budgets.period = ?
                     ORDER BY categories.name COLLATE NOCASE"""
            rows = connection.execute(sql, (parse_period(period),)).fetchall()
        else:
            sql = """SELECT budgets.*, categories.name AS category_name
                     FROM budgets JOIN categories ON categories.id = budgets.category_id
                     ORDER BY budgets.period DESC, categories.name COLLATE NOCASE"""
            rows = connection.execute(sql).fetchall()
    return JSONResponse([dict(row) for row in rows])


def _get(request: Request) -> JSONResponse:
    budget_id = path_id(request.path_params["budget_id"])
    with transaction() as connection:
        row = connection.execute("SELECT * FROM budgets WHERE id = ?", (budget_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Budget nicht gefunden")
    return JSONResponse(dict(row))


def _limit_from(payload: dict, fallback: int | None = None) -> int:
    value = check_cents(payload.get("limit_cents", fallback), "limit_cents")
    if value < 0:
        raise bad("'limit_cents' muss eine nicht negative ganze Zahl sein")
    return value


def _ensure_category(connection, category_id: int) -> None:
    if (
        connection.execute("SELECT 1 FROM categories WHERE id = ?", (category_id,)).fetchone()
        is None
    ):
        raise bad("'category_id' verweist auf keine bestehende Kategorie")


async def _create(request: Request) -> JSONResponse:
    payload = await json_object(request)
    category_id = required_int(payload, "category_id")
    period = parse_period(payload.get("period"))
    limit_cents = _limit_from(payload)
    try:
        with transaction() as connection:
            _ensure_category(connection, category_id)
            cursor = connection.execute(
                "INSERT INTO budgets (category_id, period, limit_cents) VALUES (?, ?, ?)",
                (category_id, period, limit_cents),
            )
            row = connection.execute(
                "SELECT * FROM budgets WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=409, detail="Für diese Kategorie und diesen Monat gibt es schon ein Budget"
        ) from exc
    return JSONResponse(dict(row), status_code=201)


async def _update(request: Request) -> JSONResponse:
    budget_id = path_id(request.path_params["budget_id"])
    payload = await json_object(request)
    try:
        with transaction() as connection:
            row = connection.execute("SELECT * FROM budgets WHERE id = ?", (budget_id,)).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Budget nicht gefunden")

            category_id = (
                required_int(payload, "category_id")
                if "category_id" in payload
                else row["category_id"]
            )
            period = parse_period(payload["period"]) if "period" in payload else row["period"]
            limit_cents = _limit_from(payload, row["limit_cents"])
            _ensure_category(connection, category_id)
            connection.execute(
                "UPDATE budgets SET category_id = ?, period = ?, limit_cents = ? WHERE id = ?",
                (category_id, period, limit_cents, budget_id),
            )
            updated = connection.execute(
                "SELECT * FROM budgets WHERE id = ?", (budget_id,)
            ).fetchone()
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=409, detail="Für diese Kategorie und diesen Monat gibt es schon ein Budget"
        ) from exc
    return JSONResponse(dict(updated))


def _delete(request: Request) -> Response:
    budget_id = path_id(request.path_params["budget_id"])
    with transaction() as connection:
        cursor = connection.execute("DELETE FROM budgets WHERE id = ?", (budget_id,))
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Budget nicht gefunden")
    return Response(status_code=204)


routes = [
    Route("/api/budgets", _list, methods=["GET"]),
    Route("/api/budgets", _create, methods=["POST"]),
    Route("/api/budgets/{budget_id}", _get, methods=["GET"]),
    Route("/api/budgets/{budget_id}", _update, methods=["PUT"]),
    Route("/api/budgets/{budget_id}", _delete, methods=["DELETE"]),
]
