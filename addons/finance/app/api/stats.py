"""Lesende API für Auswertungen (gleiche Zahlen wie die Oberfläche)."""

from __future__ import annotations

from reports import balance_history, budget_progress, category_breakdown, monthly_comparison
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from validation import bad, parse_period


def _count(request: Request) -> int:
    try:
        count = int(request.query_params.get("months", "6"))
    except ValueError as exc:
        raise bad("'months' muss eine ganze Zahl sein") from exc
    if not 1 <= count <= 24:
        raise bad("'months' muss zwischen 1 und 24 liegen")
    return count


def _optional_period(request: Request, key: str = "period") -> str | None:
    value = request.query_params.get(key)
    return parse_period(value) if value else None


def monthly(request: Request) -> JSONResponse:
    end = _optional_period(request, "end_period")
    return JSONResponse(monthly_comparison(_count(request), end))


def categories(request: Request) -> JSONResponse:
    kind = request.query_params.get("type", "expense")
    if kind not in ("expense", "income"):
        raise bad("'type' muss 'expense' oder 'income' sein")
    return JSONResponse(category_breakdown(_optional_period(request), kind))


def budgets(request: Request) -> JSONResponse:
    return JSONResponse(budget_progress(_optional_period(request)))


def balance(request: Request) -> JSONResponse:
    end = _optional_period(request, "end_period")
    return JSONResponse(balance_history(_count(request), end))


routes = [
    Route("/api/stats/monthly", monthly, methods=["GET"]),
    Route("/api/stats/categories", categories, methods=["GET"]),
    Route("/api/stats/budgets", budgets, methods=["GET"]),
    Route("/api/stats/balance", balance, methods=["GET"]),
]
