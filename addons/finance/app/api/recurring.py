"""Interne API für wiederkehrende Buchungen (Fixkosten)."""

from __future__ import annotations

import recurring
from recurring import RecurringError
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


def _choice(value: object, key: str, allowed: tuple[str, ...]) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise bad(f"'{key}' muss einer von {', '.join(allowed)} sein")
    return value


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

    direction = take("direction", lambda v: _choice(v, "direction", recurring.DIRECTIONS))

    if direction == "transfer":
        if "to_account_id" in payload:
            to_account_id = required_int(
                {"to_account_id": payload["to_account_id"]}, "to_account_id"
            )
        elif old is not None:
            to_account_id = old["to_account_id"]
        else:
            raise bad("'to_account_id' ist erforderlich")
    else:
        if payload.get("to_account_id") is not None:
            raise bad("'to_account_id' darf nur bei direction='transfer' angegeben werden")
        to_account_id = None

    return {
        "name": take("name", lambda v: required_str({"name": v}, "name")),
        "amount_cents": take("amount_cents", _positive_cents),
        "direction": direction,
        "interval": take("interval", lambda v: _choice(v, "interval", recurring.INTERVALS)),
        "account_id": take("account_id", lambda v: required_int({"account_id": v}, "account_id")),
        "to_account_id": to_account_id,
        "category_id": (
            None if direction == "transfer" else take("category_id", _optional_id, required=False)
        ),
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
    return JSONResponse(recurring.list_rules())


def _get(request: Request) -> JSONResponse:
    rule = recurring.get_rule(path_id(request.path_params["rule_id"]))
    if rule is None:
        raise HTTPException(status_code=404, detail="Regel nicht gefunden")
    return JSONResponse(rule)


async def _create(request: Request) -> JSONResponse:
    values = _values(await json_object(request))
    try:
        rule_id = recurring.create_rule(values)
    except RecurringError as exc:
        raise bad(str(exc)) from exc
    recurring.generate_due()
    return JSONResponse(recurring.get_rule(rule_id), status_code=201)


async def _update(request: Request) -> JSONResponse:
    rule_id = path_id(request.path_params["rule_id"])
    old = recurring.get_rule(rule_id)
    if old is None:
        raise HTTPException(status_code=404, detail="Regel nicht gefunden")
    values = _values(await json_object(request), old)
    try:
        recurring.update_rule(rule_id, values)
    except RecurringError as exc:
        raise bad(str(exc)) from exc
    recurring.generate_due()
    return JSONResponse(recurring.get_rule(rule_id))


def _delete(request: Request) -> Response:
    try:
        recurring.delete_rule(path_id(request.path_params["rule_id"]))
    except RecurringError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(status_code=204)


routes = [
    Route("/api/recurring", _list, methods=["GET"]),
    Route("/api/recurring", _create, methods=["POST"]),
    Route("/api/recurring/{rule_id}", _get, methods=["GET"]),
    Route("/api/recurring/{rule_id}", _update, methods=["PUT"]),
    Route("/api/recurring/{rule_id}", _delete, methods=["DELETE"]),
]
