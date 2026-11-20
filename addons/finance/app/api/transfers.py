"""Interne API für Umbuchungen zwischen Konten."""

from __future__ import annotations

import transfers
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from transfers import TransferError
from validation import (
    amount_from_payload,
    bad,
    json_object,
    optional_str,
    parse_date,
    path_id,
    required_int,
)


def _positive_cents(payload: dict) -> int:
    cents = amount_from_payload(payload)
    if cents <= 0:
        raise bad("Der Betrag muss größer als 0 sein")
    return cents


def _values(payload: dict, old: dict | None = None) -> dict:
    """Payload validieren; fehlende Felder kommen vom bestehenden Datensatz."""

    def take(key: str, parser):
        if key in payload:
            return parser(payload[key])
        if old is not None:
            return old[key]
        raise bad(f"'{key}' ist erforderlich")

    return {
        "booking_date": take("booking_date", lambda value: parse_date(value)),
        "amount_cents": _positive_cents(payload)
        if old is None
        else (
            _positive_cents(payload)
            if "amount" in payload or "amount_cents" in payload
            else old["amount_cents"]
        ),
        "from_account_id": take(
            "from_account_id", lambda value: required_int(payload, "from_account_id")
        ),
        "to_account_id": take(
            "to_account_id", lambda value: required_int(payload, "to_account_id")
        ),
        "description": (
            optional_str(payload, "description", 500)
            if "description" in payload
            else (old["description"] if old is not None else "")
        ),
    }


def _list(request: Request) -> JSONResponse:
    return JSONResponse(transfers.list_transfers())


def _get(request: Request) -> JSONResponse:
    transfer = transfers.get_transfer(path_id(request.path_params["transfer_id"]))
    if transfer is None:
        raise HTTPException(status_code=404, detail="Umbuchung nicht gefunden")
    return JSONResponse(transfer)


async def _create(request: Request) -> JSONResponse:
    values = _values(await json_object(request))
    try:
        transfer_id = transfers.create_transfer(values)
    except TransferError as exc:
        raise bad(str(exc)) from exc
    return JSONResponse(transfers.get_transfer(transfer_id), status_code=201)


async def _update(request: Request) -> JSONResponse:
    transfer_id = path_id(request.path_params["transfer_id"])
    old = transfers.get_transfer(transfer_id)
    if old is None:
        raise HTTPException(status_code=404, detail="Umbuchung nicht gefunden")
    values = _values(await json_object(request), old)
    try:
        transfers.update_transfer(transfer_id, values)
    except TransferError as exc:
        raise bad(str(exc)) from exc
    return JSONResponse(transfers.get_transfer(transfer_id))


def _delete(request: Request) -> Response:
    transfer_id = path_id(request.path_params["transfer_id"])
    if transfers.get_transfer(transfer_id) is None:
        raise HTTPException(status_code=404, detail="Umbuchung nicht gefunden")
    transfers.delete_transfer(transfer_id)
    return Response(status_code=204)


routes = [
    Route("/api/transfers", _list, methods=["GET"]),
    Route("/api/transfers", _create, methods=["POST"]),
    Route("/api/transfers/{transfer_id}", _get, methods=["GET"]),
    Route("/api/transfers/{transfer_id}", _update, methods=["PUT"]),
    Route("/api/transfers/{transfer_id}", _delete, methods=["DELETE"]),
]
