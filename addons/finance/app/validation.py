"""Eingabevalidierung für die internen API-Endpunkte."""

from __future__ import annotations

import re
from datetime import date

from money import MAX_CENTS, parse_cents
from starlette.exceptions import HTTPException
from starlette.requests import Request

_PERIOD_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def bad(message: str) -> HTTPException:
    return HTTPException(status_code=400, detail=message)


async def json_object(request: Request) -> dict:
    """JSON-Objekt aus dem Request lesen oder 400 zurückgeben."""
    try:
        payload = await request.json()
    except Exception as exc:
        raise bad("Ungültiges JSON") from exc
    if not isinstance(payload, dict):
        raise bad("Ein JSON-Objekt wird erwartet")
    return payload


def required_str(payload: dict, key: str, max_length: int = 200) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise bad(f"'{key}' muss ein nicht leerer Text sein")
    value = value.strip()
    if len(value) > max_length:
        raise bad(f"'{key}' darf höchstens {max_length} Zeichen haben")
    return value


def optional_str(payload: dict, key: str, max_length: int = 500) -> str:
    value = payload.get(key, "")
    if value is None:
        return ""
    if not isinstance(value, str):
        raise bad(f"'{key}' muss ein Text sein")
    if len(value) > max_length:
        raise bad(f"'{key}' darf höchstens {max_length} Zeichen haben")
    return value.strip()


def required_int(payload: dict, key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise bad(f"'{key}' muss eine positive ganze Zahl sein")
    return value


def path_id(value: str) -> int:
    try:
        result = int(value)
    except ValueError as exc:
        raise bad("Ungültige ID") from exc
    if result <= 0:
        raise bad("Ungültige ID")
    return result


def query_int(query, key: str) -> int:
    """Positive ganze Zahl aus einem Query-Parameter lesen."""
    try:
        result = int(query[key])
    except (ValueError, TypeError) as exc:
        raise bad(f"'{key}' muss eine ganze Zahl sein") from exc
    if result <= 0:
        raise bad(f"'{key}' muss eine positive ganze Zahl sein")
    return result


def parse_date(value: object, key: str = "booking_date") -> str:
    if not isinstance(value, str):
        raise bad(f"'{key}' muss ein Datum im Format JJJJ-MM-TT sein")
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise bad(f"'{key}' muss ein gültiges Datum im Format JJJJ-MM-TT sein") from exc


def parse_period(value: object) -> str:
    if not isinstance(value, str) or not _PERIOD_RE.fullmatch(value):
        raise bad("'period' muss im Format JJJJ-MM sein")
    return value


def check_cents(value: object, key: str) -> int:
    """Ganzzahlige Cent mit Obergrenze prüfen (schützt vor SQLite-Overflow)."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise bad(f"'{key}' muss eine ganze Zahl in Cent sein")
    if abs(value) > MAX_CENTS:
        raise bad(f"'{key}' ist zu groß")
    return value


def amount_from_payload(payload: dict) -> int:
    """Betrag aus 'amount' (Text) oder 'amount_cents' (Zahl) lesen."""
    if "amount" in payload:
        try:
            return parse_cents(payload["amount"])
        except ValueError as exc:
            raise bad(str(exc)) from exc
    if "amount_cents" in payload:
        value = check_cents(payload["amount_cents"], "amount_cents")
        if value == 0:
            raise bad("'amount_cents' muss eine von 0 verschiedene ganze Zahl sein")
        return value
    raise bad("Einer der Schlüssel 'amount' oder 'amount_cents' ist erforderlich")
