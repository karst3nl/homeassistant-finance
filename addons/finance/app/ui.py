"""Servergerenderte Oberfläche: Dashboard, Ausgabeneingabe und Stammdaten.

Kein JavaScript, kein CDN, kein Build-Step. Alle Links sind relativ zum
Ingress-Pfad, damit die Seiten auch unter /api/hassio_ingress/<token>/ funktionieren.
"""

from __future__ import annotations

import calendar
import re
import sqlite3
from pathlib import Path
from urllib.parse import parse_qs

from charts import bar_chart, donut_chart, line_chart
from db import transaction
from money import cents_to_decimal, format_cents, parse_cents
from reports import (
    balance_history,
    budget_progress,
    category_breakdown,
    current_period,
    monthly_comparison,
    normalize_period,
    shift_period,
)
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from starlette.routing import Route
from starlette.templating import Jinja2Templates
from stats import dashboard_data, filtered_transactions
from validation import parse_date, path_id

_TEMPLATE_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=_TEMPLATE_DIR)
templates.env.filters["cents"] = format_cents
templates.env.filters["amount"] = lambda cents: f"{cents_to_decimal(cents):.2f}".replace(".", ",")

ACCOUNT_TYPES = ("checking", "savings", "cash", "credit", "investment")
CATEGORY_TYPES = ("income", "expense")
_INGRESS_PATH_RE = re.compile(r"^/[A-Za-z0-9_./-]*$")
MAX_FORM_BYTES = 64 * 1024


def _base(request: Request) -> str:
    """Ingress-Pfad als Basis für relative Links und Redirects.

    Der Header stammt vom Proxy, wird aber zusätzlich streng geprüft: ein
    Wert wie ``//evil.example`` würde sonst als externe Basis interpretiert.
    """
    value = request.headers.get("x-ingress-path", "/")
    if not _INGRESS_PATH_RE.fullmatch(value) or value.startswith("//") or ".." in value.split("/"):
        value = "/"
    return value if value.endswith("/") else value + "/"


def _render(request: Request, name: str, context: dict | None = None, status_code: int = 200):
    data = dict(context or {})
    data.setdefault("base", _base(request))
    data.setdefault("errors", [])
    data.setdefault("form", {})
    return templates.TemplateResponse(request, name, data, status_code=status_code)


def _redirect(request: Request, target: str = "") -> RedirectResponse:
    return RedirectResponse(_base(request) + target, status_code=303)


async def _form(request: Request) -> dict[str, str]:
    """URL-kodiertes Formular ohne zusätzliche Abhängigkeit lesen."""
    body = await request.body()
    if len(body) > MAX_FORM_BYTES:
        raise HTTPException(status_code=413, detail="Formular zu groß")
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="Ungültige Zeichen im Formular") from exc
    return {key: values[0] for key, values in parse_qs(text, keep_blank_values=True).items()}


def _positive_id(value: str) -> int | None:
    try:
        result = int(value)
    except ValueError:
        return None
    return result if result > 0 else None


def _account_options() -> list[dict]:
    with transaction() as connection:
        rows = connection.execute(
            "SELECT id, name FROM accounts WHERE active = 1 ORDER BY name COLLATE NOCASE"
        ).fetchall()
    return [dict(row) for row in rows]


def _period(request: Request) -> str:
    """Gewählten Monat aus der URL lesen, sonst den aktuellen."""
    try:
        return normalize_period(request.query_params.get("period", current_period()))
    except ValueError:
        return current_period()


def _period_label(period: str) -> str:
    year, month = period.split("-")
    return f"{calendar.month_name[int(month)]} {year}"


def _expense_categories() -> list[dict]:
    with transaction() as connection:
        rows = connection.execute(
            "SELECT id, name FROM categories WHERE type = 'expense' ORDER BY name COLLATE NOCASE"
        ).fetchall()
    return [dict(row) for row in rows]


def _budget_context(period: str) -> dict:
    return {
        "period": period,
        "period_label": _period_label(period),
        "current_period": current_period(),
        "budgets": budget_progress(period),
        "categories": _expense_categories(),
    }


def dashboard(request: Request):
    return _render(request, "dashboard.html", dashboard_data())


async def create_transaction(request: Request) -> Response:
    form = await _form(request)
    errors: list[str] = []

    account_id = _positive_id(form.get("account_id", ""))
    if account_id is None:
        errors.append("Bitte ein Konto auswählen.")

    try:
        booking_date = parse_date(form.get("booking_date", ""))
    except HTTPException:
        booking_date = ""
        errors.append("Bitte ein gültiges Datum angeben.")

    direction = form.get("direction", "expense")
    if direction not in ("expense", "income"):
        errors.append("Bitte Ausgabe oder Einnahme wählen.")
        direction = "expense"

    try:
        amount = parse_cents(form.get("amount", ""))
    except ValueError:
        amount = 0
        errors.append("Bitte einen gültigen Betrag angeben.")
    if amount <= 0:
        errors.append("Der Betrag muss größer als 0 sein.")

    category_value = form.get("category_id", "")
    category_id = _positive_id(category_value) if category_value else None

    if not errors:
        cents = -amount if direction == "expense" else amount
        try:
            with transaction() as connection:
                if (
                    connection.execute(
                        "SELECT 1 FROM accounts WHERE id = ?", (account_id,)
                    ).fetchone()
                    is None
                ):
                    raise ValueError("Das gewählte Konto existiert nicht.")
                if (
                    category_id is not None
                    and connection.execute(
                        "SELECT 1 FROM categories WHERE id = ?", (category_id,)
                    ).fetchone()
                    is None
                ):
                    raise ValueError("Die gewählte Kategorie existiert nicht.")
                connection.execute(
                    """INSERT INTO transactions
                       (account_id, booking_date, amount_cents,
                        counterparty, description, category_id)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        account_id,
                        booking_date,
                        cents,
                        form.get("counterparty", "").strip(),
                        form.get("description", "").strip(),
                        category_id,
                    ),
                )
        except ValueError as exc:
            errors.append(str(exc))

    if errors:
        return _render(
            request,
            "dashboard.html",
            {**dashboard_data(), "errors": errors, "form": form},
            status_code=400,
        )
    return _redirect(request)


def transactions_page(request: Request):
    filters = dict(request.query_params)
    return _render(
        request,
        "transactions.html",
        {
            "transactions": filtered_transactions(filters),
            "accounts": _account_options(),
            "filters": filters,
        },
    )


def delete_transaction(request: Request) -> Response:
    with transaction() as connection:
        connection.execute(
            "DELETE FROM transactions WHERE id = ?",
            (path_id(request.path_params["transaction_id"]),),
        )
    return _redirect(request, "ui/transactions")


def accounts_page(request: Request):
    return _render(request, "accounts.html", _accounts_with_balances())


async def create_account(request: Request) -> Response:
    form = await _form(request)
    errors: list[str] = []
    name = form.get("name", "").strip()
    if not name:
        errors.append("Bitte einen Kontonamen angeben.")
    account_type = form.get("type", "checking")
    if account_type not in ACCOUNT_TYPES:
        errors.append("Bitte einen gültigen Kontotyp wählen.")
    currency = form.get("currency", "EUR").strip().upper() or "EUR"
    try:
        initial_cents = parse_cents(form.get("initial_balance", "0"))
    except ValueError:
        initial_cents = 0
        errors.append("Bitte einen gültigen Anfangssaldo angeben.")

    if errors:
        return _render(
            request,
            "accounts.html",
            {**_accounts_with_balances(), "errors": errors, "form": form},
            status_code=400,
        )

    with transaction() as connection:
        connection.execute(
            """INSERT INTO accounts (name, type, currency, initial_balance_cents)
               VALUES (?, ?, ?, ?)""",
            (name, account_type, currency, initial_cents),
        )
    return _redirect(request, "ui/accounts")


def delete_account(request: Request) -> Response:
    account_id = path_id(request.path_params["account_id"])
    try:
        with transaction() as connection:
            connection.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
    except sqlite3.IntegrityError:
        return _render(
            request,
            "accounts.html",
            {
                **_accounts_with_balances(),
                "errors": [
                    "Das Konto kann nicht gelöscht werden, solange Buchungen darauf existieren."
                ],
            },
            status_code=409,
        )
    return _redirect(request, "ui/accounts")


def _accounts_with_balances() -> dict:
    with transaction() as connection:
        rows = connection.execute(
            """
            SELECT a.id, a.name, a.type, a.currency, a.active,
                   a.initial_balance_cents + COALESCE(SUM(t.amount_cents), 0) AS balance_cents
            FROM accounts a
            LEFT JOIN transactions t ON t.account_id = a.id
            GROUP BY a.id
            ORDER BY a.name COLLATE NOCASE
            """
        ).fetchall()
    return {"accounts": [dict(row) for row in rows]}


def categories_page(request: Request):
    with transaction() as connection:
        rows = connection.execute(
            "SELECT id, name, type FROM categories ORDER BY name COLLATE NOCASE"
        ).fetchall()
    return _render(request, "categories.html", {"categories": [dict(row) for row in rows]})


async def create_category(request: Request) -> Response:
    form = await _form(request)
    errors: list[str] = []
    name = form.get("name", "").strip()
    if not name:
        errors.append("Bitte einen Kategorienamen angeben.")
    category_type = form.get("type", "expense")
    if category_type not in CATEGORY_TYPES:
        errors.append("Bitte Einnahme oder Ausgabe wählen.")

    if errors:
        return _render(
            request,
            "categories.html",
            {**_categories(), "errors": errors, "form": form},
            status_code=400,
        )

    with transaction() as connection:
        connection.execute(
            "INSERT INTO categories (name, type) VALUES (?, ?)", (name, category_type)
        )
    return _redirect(request, "ui/categories")


def delete_category(request: Request) -> Response:
    with transaction() as connection:
        connection.execute(
            "DELETE FROM categories WHERE id = ?", (path_id(request.path_params["category_id"]),)
        )
    return _redirect(request, "ui/categories")


def _categories() -> dict:
    with transaction() as connection:
        rows = connection.execute(
            "SELECT id, name, type FROM categories ORDER BY name COLLATE NOCASE"
        ).fetchall()
    return {"categories": [dict(row) for row in rows]}


def reports_page(request: Request):
    period = _period(request)
    months = monthly_comparison(6, period)
    items = category_breakdown(period)
    history = balance_history(6, period)
    return _render(
        request,
        "reports.html",
        {
            **_budget_context(period),
            "months": months,
            "categories": items,
            "history": history,
            "monthly_svg": bar_chart(months),
            "donut_svg": donut_chart(items),
            "balance_svg": line_chart(history),
            "prev_period": shift_period(period, -1),
            "next_period": shift_period(period, 1),
        },
    )


def budgets_page(request: Request):
    period = _period(request)
    return _render(request, "budgets.html", _budget_context(period))


async def create_budget(request: Request) -> Response:
    form = await _form(request)
    errors: list[str] = []
    try:
        period = normalize_period(form.get("period", current_period()))
    except ValueError:
        period = current_period()
        errors.append("Bitte einen gültigen Monat angeben.")

    category_id = _positive_id(form.get("category_id", ""))
    if category_id is None:
        errors.append("Bitte eine Kategorie auswählen.")

    try:
        limit_cents = parse_cents(form.get("limit", ""))
    except ValueError:
        limit_cents = 0
        errors.append("Bitte einen gültigen Betrag angeben.")
    if limit_cents < 0:
        errors.append("Das Limit darf nicht negativ sein.")

    if not errors:
        try:
            with transaction() as connection:
                if (
                    connection.execute(
                        "SELECT 1 FROM categories WHERE id = ? AND type = 'expense'",
                        (category_id,),
                    ).fetchone()
                    is None
                ):
                    raise ValueError("Bitte eine Ausgabekategorie auswählen.")
                connection.execute(
                    "INSERT INTO budgets (category_id, period, limit_cents) VALUES (?, ?, ?)",
                    (category_id, period, limit_cents),
                )
        except sqlite3.IntegrityError:
            errors.append("Für diese Kategorie und diesen Monat gibt es schon ein Budget.")
        except ValueError as exc:
            errors.append(str(exc))

    if errors:
        return _render(
            request,
            "budgets.html",
            {**_budget_context(period), "errors": errors, "form": form},
            status_code=400,
        )
    return _redirect(request, f"ui/budgets?period={period}")


async def update_budget(request: Request) -> Response:
    budget_id = path_id(request.path_params["budget_id"])
    form = await _form(request)
    try:
        period = normalize_period(form.get("period", current_period()))
    except ValueError:
        period = current_period()
    try:
        limit_cents = parse_cents(form.get("limit", ""))
    except ValueError:
        limit_cents = -1
    if limit_cents < 0:
        return _render(
            request,
            "budgets.html",
            {
                **_budget_context(period),
                "errors": ["Bitte einen gültigen, nicht negativen Betrag angeben."],
            },
            status_code=400,
        )

    with transaction() as connection:
        connection.execute(
            "UPDATE budgets SET limit_cents = ? WHERE id = ?", (limit_cents, budget_id)
        )
    return _redirect(request, f"ui/budgets?period={period}")


def delete_budget(request: Request) -> Response:
    budget_id = path_id(request.path_params["budget_id"])
    with transaction() as connection:
        connection.execute("DELETE FROM budgets WHERE id = ?", (budget_id,))
    period = _period(request)
    return _redirect(request, f"ui/budgets?period={period}")


routes = [
    Route("/", dashboard, methods=["GET"]),
    Route("/ui/transactions", transactions_page, methods=["GET"]),
    Route("/ui/transactions", create_transaction, methods=["POST"]),
    Route("/ui/transactions/{transaction_id}/delete", delete_transaction, methods=["POST"]),
    Route("/ui/accounts", accounts_page, methods=["GET"]),
    Route("/ui/accounts", create_account, methods=["POST"]),
    Route("/ui/accounts/{account_id}/delete", delete_account, methods=["POST"]),
    Route("/ui/categories", categories_page, methods=["GET"]),
    Route("/ui/categories", create_category, methods=["POST"]),
    Route("/ui/categories/{category_id}/delete", delete_category, methods=["POST"]),
    Route("/ui/reports", reports_page, methods=["GET"]),
    Route("/ui/budgets", budgets_page, methods=["GET"]),
    Route("/ui/budgets", create_budget, methods=["POST"]),
    Route("/ui/budgets/{budget_id}", update_budget, methods=["POST"]),
    Route("/ui/budgets/{budget_id}/delete", delete_budget, methods=["POST"]),
]
