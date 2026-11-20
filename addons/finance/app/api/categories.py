"""CRUD-Endpunkte für Kategorien."""

from __future__ import annotations

from db import transaction
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from validation import bad, json_object, optional_str, path_id, required_int, required_str

CATEGORY_TYPES = frozenset({"income", "expense"})


def _list(request: Request) -> JSONResponse:
    with transaction() as connection:
        rows = connection.execute(
            "SELECT * FROM categories ORDER BY type, name COLLATE NOCASE"
        ).fetchall()
    return JSONResponse([dict(row) for row in rows])


def _get(request: Request) -> JSONResponse:
    category_id = path_id(request.path_params["category_id"])
    with transaction() as connection:
        row = connection.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Kategorie nicht gefunden")
    return JSONResponse(dict(row))


def _type_from(payload: dict, fallback: str) -> str:
    category_type = payload.get("type", fallback)
    if category_type not in CATEGORY_TYPES:
        raise bad("'type' muss 'income' oder 'expense' sein")
    return category_type


def _parent_from(payload: dict, fallback: int | None) -> int | None:
    if "parent_id" not in payload:
        return fallback
    value = payload["parent_id"]
    if value is None:
        return None
    return required_int(payload, "parent_id")


async def _create(request: Request) -> JSONResponse:
    payload = await json_object(request)
    name = required_str(payload, "name")
    category_type = _type_from(payload, "expense")
    parent_id = _parent_from(payload, None)
    color = optional_str(payload, "color", 20) or None
    icon = optional_str(payload, "icon", 100) or None

    with transaction() as connection:
        if (
            parent_id is not None
            and connection.execute("SELECT 1 FROM categories WHERE id = ?", (parent_id,)).fetchone()
            is None
        ):
            raise bad("'parent_id' verweist auf keine bestehende Kategorie")
        cursor = connection.execute(
            """INSERT INTO categories (name, parent_id, type, color, icon)
               VALUES (?, ?, ?, ?, ?)""",
            (name, parent_id, category_type, color, icon),
        )
        row = connection.execute(
            "SELECT * FROM categories WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
    return JSONResponse(dict(row), status_code=201)


async def _update(request: Request) -> JSONResponse:
    category_id = path_id(request.path_params["category_id"])
    payload = await json_object(request)
    with transaction() as connection:
        row = connection.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Kategorie nicht gefunden")

        name = required_str(payload, "name") if "name" in payload else row["name"]
        category_type = _type_from(payload, row["type"])
        parent_id = _parent_from(payload, row["parent_id"])
        if parent_id == category_id:
            raise bad("Eine Kategorie kann nicht ihr eigenes Elternteil sein")
        if (
            parent_id is not None
            and connection.execute("SELECT 1 FROM categories WHERE id = ?", (parent_id,)).fetchone()
            is None
        ):
            raise bad("'parent_id' verweist auf keine bestehende Kategorie")
        color = optional_str(payload, "color", 20) or None if "color" in payload else row["color"]
        icon = optional_str(payload, "icon", 100) or None if "icon" in payload else row["icon"]

        connection.execute(
            """UPDATE categories
               SET name = ?, parent_id = ?, type = ?, color = ?, icon = ?
               WHERE id = ?""",
            (name, parent_id, category_type, color, icon, category_id),
        )
        updated = connection.execute(
            "SELECT * FROM categories WHERE id = ?", (category_id,)
        ).fetchone()
    return JSONResponse(dict(updated))


def _delete(request: Request) -> Response:
    category_id = path_id(request.path_params["category_id"])
    with transaction() as connection:
        cursor = connection.execute("DELETE FROM categories WHERE id = ?", (category_id,))
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Kategorie nicht gefunden")
    return Response(status_code=204)


routes = [
    Route("/api/categories", _list, methods=["GET"]),
    Route("/api/categories", _create, methods=["POST"]),
    Route("/api/categories/{category_id}", _get, methods=["GET"]),
    Route("/api/categories/{category_id}", _update, methods=["PUT"]),
    Route("/api/categories/{category_id}", _delete, methods=["DELETE"]),
]
