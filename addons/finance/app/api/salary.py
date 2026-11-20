"""Interne API für das Monatsgehalt (eigener Bereich neben den Fixkosten)."""

from __future__ import annotations

import salary
from salary import SalaryError
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from validation import (
    bad,
    check_cents,
    json_object,
    optional_str,
    parse_date,
    path_id,
    required_int,
    required_str,
)


def _positive_cents(value: object) -> int:
    cents = check_cents(value, "amount_cents")
    if cents <= 0:
        raise bad("'amount_cents' muss größer als 0 sein")
    return cents


def _optional_id(value: object) -> int | None:
    return None if value is None else required_int({"category_id": value}, "category_id")


def _active(value: object) -> int:
    if isinstance(value, bool) or value in (0, 1):
        return int(value)
    raise bad("'active' muss wahr oder falsch sein")


def _values(payload: dict, old: dict | None = None) -> dict:
    """Payload validieren; fehlende Felder kommen vom bestehenden Datensatz."""

    def take(key: str, parser, required: bool = True):
        if key in payload:
            return parser(payload[key])
        if old is not None:
            return old[key]
        if required:
            raise bad(f"'{key}' ist erforderlich")
        return None

    def optional_text(key: str, limit: int) -> str:
        return take(key, lambda v: optional_str({key: v}, key, limit), required=False) or ""

    return {
        "name": take("name", lambda v: required_str({"name": v}, "name")),
        "amount_cents": take("amount_cents", _positive_cents),
        "account_id": take("account_id", lambda v: required_int({"account_id": v}, "account_id")),
        "category_id": take("category_id", _optional_id, required=False),
        "start_date": take("start_date", lambda v: parse_date(v, "start_date")),
        "counterparty": optional_text("counterparty", 200),
        "description": optional_text("description", 500),
        "active": (
            _active(payload["active"])
            if "active" in payload
            else (old["active"] if old is not None else 1)
        ),
    }


def _list(request: Request) -> JSONResponse:
    return JSONResponse(salary.list_rules())


def _get(request: Request) -> JSONResponse:
    rule = salary.get_rule(path_id(request.path_params["rule_id"]))
    if rule is None:
        raise HTTPException(status_code=404, detail="Gehaltsregel nicht gefunden")
    return JSONResponse(rule)


async def _create(request: Request) -> JSONResponse:
    values = _values(await json_object(request))
    try:
        rule_id = salary.create_rule(values)
    except SalaryError as exc:
        raise bad(str(exc)) from exc
    salary.generate_due()
    return JSONResponse(salary.get_rule(rule_id), status_code=201)


async def _update(request: Request) -> JSONResponse:
    rule_id = path_id(request.path_params["rule_id"])
    old = salary.get_rule(rule_id)
    if old is None:
        raise HTTPException(status_code=404, detail="Gehaltsregel nicht gefunden")
    values = _values(await json_object(request), old)
    try:
        salary.update_rule(rule_id, values)
    except SalaryError as exc:
        raise bad(str(exc)) from exc
    salary.generate_due()
    return JSONResponse(salary.get_rule(rule_id))


def _delete(request: Request) -> Response:
    try:
        salary.delete_rule(path_id(request.path_params["rule_id"]))
    except SalaryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(status_code=204)


routes = [
    Route("/api/salary", _list, methods=["GET"]),
    Route("/api/salary", _create, methods=["POST"]),
    Route("/api/salary/{rule_id}", _get, methods=["GET"]),
    Route("/api/salary/{rule_id}", _update, methods=["PUT"]),
    Route("/api/salary/{rule_id}", _delete, methods=["DELETE"]),
]
