"""Servergerenderte Oberfläche: Dashboard, Ausgabeneingabe und Stammdaten.

Kein JavaScript, kein CDN, kein Build-Step. Alle Links sind relativ zum
Ingress-Pfad, damit die Seiten auch unter /api/hassio_ingress/<token>/ funktionieren.
"""

from __future__ import annotations

import calendar
import re
import sqlite3
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs

import backup
import recurring
import salary
import transfers
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
from starlette.background import BackgroundTask
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import FileResponse, RedirectResponse, Response
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


_NAV_PREFIXES = (
    ("ui/transactions", "transactions"),
    ("ui/transfers", "transfers"),
    ("ui/budgets", "budgets"),
    ("ui/recurring", "recurring"),
    ("ui/salary", "salary"),
    ("ui/reports", "reports"),
    ("ui/accounts", "accounts"),
    ("ui/categories", "categories"),
    ("ui/backups", "backups"),
)


def _active_nav(request: Request) -> str:
    """Schlüssel des aktiven Menüeintrags aus dem aktuellen Pfad ableiten."""
    path = request.url.path
    base = _base(request).rstrip("/")
    if base and path.startswith(base + "/"):
        path = path[len(base) :]
    path = path.lstrip("/")
    if not path:
        return "overview"
    for prefix, key in _NAV_PREFIXES:
        if path == prefix or path.startswith(prefix + "/"):
            return key
    return ""


def _render(request: Request, name: str, context: dict | None = None, status_code: int = 200):
    data = dict(context or {})
    data.setdefault("base", _base(request))
    data.setdefault("active_nav", _active_nav(request))
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


def _amount_input(cents: int) -> str:
    """Betrag für ein Textfeld – ohne Tausendertrennzeichen, mit Komma."""
    return f"{cents_to_decimal(abs(cents)):.2f}".replace(".", ",")


def _format_size(num_bytes: int) -> str:
    value = num_bytes / 1024
    unit = "KiB"
    if value >= 1024:
        value /= 1024
        unit = "MiB"
    return f"{value:.1f} {unit}"


def _check_form_references(connection, account_id: int, category_id: int | None) -> None:
    if connection.execute("SELECT 1 FROM accounts WHERE id = ?", (account_id,)).fetchone() is None:
        raise ValueError("Das gewählte Konto existiert nicht.")
    if (
        category_id is not None
        and connection.execute("SELECT 1 FROM categories WHERE id = ?", (category_id,)).fetchone()
        is None
    ):
        raise ValueError("Die gewählte Kategorie existiert nicht.")


def _all_categories() -> list[dict]:
    with transaction() as connection:
        rows = connection.execute(
            "SELECT id, name, type FROM categories ORDER BY name COLLATE NOCASE"
        ).fetchall()
    return [dict(row) for row in rows]


def _income_categories() -> list[dict]:
    return [category for category in _all_categories() if category["type"] == "income"]


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
    return _render(request, "dashboard.html", {**dashboard_data(), "categories": _all_categories()})


def _transaction_values(form: dict[str, str]) -> tuple[dict, list[str]]:
    """Formularwerte einer Buchung validieren (anlegen und bearbeiten)."""
    errors: list[str] = []

    account_id = _positive_id(form.get("account_id", ""))
    if account_id is None:
        errors.append("Bitte ein Konto auswählen.")

    try:
        booking_date = parse_date(form.get("booking_date", ""), "booking_date")
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

    values = {
        "account_id": account_id,
        "booking_date": booking_date,
        "amount_cents": -amount if direction == "expense" else amount,
        "counterparty": form.get("counterparty", "").strip(),
        "description": form.get("description", "").strip(),
        "category_id": category_id,
    }
    return values, errors


async def create_transaction(request: Request) -> Response:
    form = await _form(request)
    values, errors = _transaction_values(form)

    if not errors:
        try:
            with transaction() as connection:
                _check_form_references(connection, values["account_id"], values["category_id"])
                connection.execute(
                    """INSERT INTO transactions
                       (account_id, booking_date, amount_cents,
                        counterparty, description, category_id)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        values["account_id"],
                        values["booking_date"],
                        values["amount_cents"],
                        values["counterparty"],
                        values["description"],
                        values["category_id"],
                    ),
                )
        except ValueError as exc:
            errors.append(str(exc))

    if errors:
        return _render(
            request,
            "dashboard.html",
            {
                **dashboard_data(),
                "categories": _all_categories(),
                "errors": errors,
                "form": form,
                "active_nav": "overview",
            },
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
                detail="Umbuchungen müssen unter Umbuchungen gelöscht werden.",
            )
        connection.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))
    return _redirect(request, "ui/transactions")


def _transaction_edit_context(transaction_id: int, form: dict | None = None) -> dict:
    with transaction() as connection:
        row = connection.execute(
            "SELECT * FROM transactions WHERE id = ?", (transaction_id,)
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Buchung nicht gefunden")
    entry = dict(row)
    if form is None:
        form = {
            **entry,
            "direction": "income" if entry["amount_cents"] > 0 else "expense",
            "amount": _amount_input(entry["amount_cents"]),
            "account_id": str(entry["account_id"]),
            "category_id": str(entry["category_id"]) if entry["category_id"] else "",
        }
    return {
        "entry": entry,
        "accounts": _account_options(),
        "categories": _all_categories(),
        "today": date.today().isoformat(),
        "form": form,
    }


def edit_transaction_page(request: Request):
    transaction_id = path_id(request.path_params["transaction_id"])
    with transaction() as connection:
        row = connection.execute(
            "SELECT transfer_id FROM transactions WHERE id = ?", (transaction_id,)
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Buchung nicht gefunden")
    if row["transfer_id"] is not None:
        return _redirect(request, f"ui/transfers/{row['transfer_id']}/edit")
    return _render(request, "transaction_edit.html", _transaction_edit_context(transaction_id))


async def update_transaction(request: Request) -> Response:
    transaction_id = path_id(request.path_params["transaction_id"])
    with transaction() as connection:
        existing = connection.execute(
            "SELECT transfer_id FROM transactions WHERE id = ?", (transaction_id,)
        ).fetchone()
    if existing is None:
        raise HTTPException(status_code=404, detail="Buchung nicht gefunden")
    if existing["transfer_id"] is not None:
        raise HTTPException(
            status_code=409,
            detail="Umbuchungen müssen unter Umbuchungen bearbeitet werden.",
        )
    form = await _form(request)
    values, errors = _transaction_values(form)
    if not errors:
        try:
            with transaction() as connection:
                if (
                    connection.execute(
                        "SELECT 1 FROM transactions WHERE id = ?", (transaction_id,)
                    ).fetchone()
                    is None
                ):
                    raise HTTPException(status_code=404, detail="Buchung nicht gefunden")
                _check_form_references(connection, values["account_id"], values["category_id"])
                connection.execute(
                    """UPDATE transactions SET
                           account_id = ?, booking_date = ?, amount_cents = ?,
                           counterparty = ?, description = ?, category_id = ?,
                           updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                       WHERE id = ?""",
                    (
                        values["account_id"],
                        values["booking_date"],
                        values["amount_cents"],
                        values["counterparty"],
                        values["description"],
                        values["category_id"],
                        transaction_id,
                    ),
                )
        except ValueError as exc:
            errors.append(str(exc))

    if errors:
        return _render(
            request,
            "transaction_edit.html",
            {**_transaction_edit_context(transaction_id, form), "errors": errors},
            status_code=400,
        )
    return _redirect(request, "ui/transactions")


def _transfer_values(form: dict[str, str]) -> tuple[dict, list[str]]:
    """Formularwerte einer Umbuchung validieren (anlegen und bearbeiten)."""
    errors: list[str] = []

    from_account_id = _positive_id(form.get("from_account_id", ""))
    to_account_id = _positive_id(form.get("to_account_id", ""))
    if from_account_id is None:
        errors.append("Bitte ein Quellkonto auswählen.")
    if to_account_id is None:
        errors.append("Bitte ein Zielkonto auswählen.")
    if from_account_id and to_account_id and from_account_id == to_account_id:
        errors.append("Quell- und Zielkonto müssen unterschiedlich sein.")

    try:
        booking_date = parse_date(form.get("booking_date", ""), "booking_date")
    except HTTPException:
        booking_date = ""
        errors.append("Bitte ein gültiges Datum angeben.")

    try:
        amount = parse_cents(form.get("amount", ""))
    except ValueError:
        amount = 0
        errors.append("Bitte einen gültigen Betrag angeben.")
    if amount <= 0:
        errors.append("Der Betrag muss größer als 0 sein.")

    values = {
        "booking_date": booking_date,
        "amount_cents": amount,
        "from_account_id": from_account_id,
        "to_account_id": to_account_id,
        "description": form.get("description", "").strip(),
    }
    return values, errors


def _transfer_context() -> dict:
    return {
        "transfers": transfers.list_transfers(),
        "accounts": _account_options(),
        "today": date.today().isoformat(),
    }


def transfers_page(request: Request):
    return _render(request, "transfers.html", _transfer_context())


async def create_transfer(request: Request) -> Response:
    form = await _form(request)
    values, errors = _transfer_values(form)
    if not errors:
        try:
            transfers.create_transfer(values)
        except transfers.TransferError as exc:
            errors.append(str(exc))

    if errors:
        return _render(
            request,
            "transfers.html",
            {**_transfer_context(), "errors": errors, "form": form},
            status_code=400,
        )
    return _redirect(request, "ui/transfers")


def _transfer_edit_context(transfer_id: int, form: dict | None = None) -> dict:
    transfer = transfers.get_transfer(transfer_id)
    if transfer is None:
        raise HTTPException(status_code=404, detail="Umbuchung nicht gefunden")
    if form is None:
        form = {
            **transfer,
            "amount": _amount_input(transfer["amount_cents"]),
            "from_account_id": str(transfer["from_account_id"]),
            "to_account_id": str(transfer["to_account_id"]),
        }
    return {**_transfer_context(), "transfer": transfer, "form": form}


def edit_transfer_page(request: Request):
    transfer_id = path_id(request.path_params["transfer_id"])
    return _render(request, "transfer_edit.html", _transfer_edit_context(transfer_id))


async def update_transfer(request: Request) -> Response:
    transfer_id = path_id(request.path_params["transfer_id"])
    if transfers.get_transfer(transfer_id) is None:
        raise HTTPException(status_code=404, detail="Umbuchung nicht gefunden")
    form = await _form(request)
    values, errors = _transfer_values(form)
    if not errors:
        try:
            transfers.update_transfer(transfer_id, values)
        except transfers.TransferError as exc:
            errors.append(str(exc))

    if errors:
        return _render(
            request,
            "transfer_edit.html",
            {**_transfer_edit_context(transfer_id, form), "errors": errors},
            status_code=400,
        )
    return _redirect(request, "ui/transfers")


def delete_transfer(request: Request) -> Response:
    try:
        transfers.delete_transfer(path_id(request.path_params["transfer_id"]))
    except transfers.TransferError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _redirect(request, "ui/transfers")


def accounts_page(request: Request):
    return _render(request, "accounts.html", _accounts_with_balances())


def _account_values(form: dict[str, str]) -> tuple[dict, list[str]]:
    """Formularwerte eines Kontos validieren (anlegen und bearbeiten)."""
    errors: list[str] = []
    name = form.get("name", "").strip()
    if not name:
        errors.append("Bitte einen Kontonamen angeben.")
    account_type = form.get("type", "checking")
    if account_type not in ACCOUNT_TYPES:
        errors.append("Bitte einen gültigen Kontotyp wählen.")
        account_type = "checking"
    currency = form.get("currency", "EUR").strip().upper() or "EUR"
    try:
        initial_cents = parse_cents(form.get("initial_balance", "0"))
    except ValueError:
        initial_cents = 0
        errors.append("Bitte einen gültigen Anfangssaldo angeben.")

    values = {
        "name": name,
        "type": account_type,
        "currency": currency,
        "initial_balance_cents": initial_cents,
        "active": 1 if form.get("active", "1") == "1" else 0,
    }
    return values, errors


async def create_account(request: Request) -> Response:
    form = await _form(request)
    values, errors = _account_values(form)

    if errors:
        return _render(
            request,
            "accounts.html",
            {**_accounts_with_balances(), "errors": errors, "form": form},
            status_code=400,
        )

    with transaction() as connection:
        connection.execute(
            """INSERT INTO accounts (name, type, currency, initial_balance_cents, active)
               VALUES (?, ?, ?, ?, ?)""",
            (
                values["name"],
                values["type"],
                values["currency"],
                values["initial_balance_cents"],
                values["active"],
            ),
        )
    return _redirect(request, "ui/accounts")


def edit_account_page(request: Request):
    account_id = path_id(request.path_params["account_id"])
    with transaction() as connection:
        row = connection.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Konto nicht gefunden")
    account = dict(row)
    form = {
        **account,
        "initial_balance": _amount_input(account["initial_balance_cents"]),
        "active": "1" if account["active"] else "0",
    }
    return _render(
        request,
        "account_edit.html",
        {**_accounts_with_balances(), "account": account, "form": form},
    )


async def update_account(request: Request) -> Response:
    account_id = path_id(request.path_params["account_id"])
    form = await _form(request)
    values, errors = _account_values(form)

    with transaction() as connection:
        if (
            connection.execute("SELECT 1 FROM accounts WHERE id = ?", (account_id,)).fetchone()
            is None
        ):
            raise HTTPException(status_code=404, detail="Konto nicht gefunden")
        if not errors:
            connection.execute(
                """UPDATE accounts SET name = ?, type = ?, currency = ?,
                       initial_balance_cents = ?, active = ?
                   WHERE id = ?""",
                (
                    values["name"],
                    values["type"],
                    values["currency"],
                    values["initial_balance_cents"],
                    values["active"],
                    account_id,
                ),
            )

    if errors:
        return _render(
            request,
            "account_edit.html",
            {
                **_accounts_with_balances(),
                "account": {"id": account_id, "name": values["name"]},
                "errors": errors,
                "form": form,
            },
            status_code=400,
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
                    "Das Konto kann nicht gelöscht werden, solange Buchungen darauf existieren "
                    "(auch geplante Fixkosten und Umbuchungen zählen)."
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
    return {"categories": _all_categories()}


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


def _recurring_context() -> dict:
    return {
        "rules": recurring.list_rules(),
        "accounts": _account_options(),
        "categories": _all_categories(),
        "summary": recurring.planned_summary(),
        "today": date.today().isoformat(),
    }


def recurring_page(request: Request):
    return _render(request, "recurring.html", _recurring_context())


def _recurring_values(form: dict[str, str]) -> tuple[dict, list[str]]:
    """Formularwerte einer Fixkosten-Regel validieren."""
    errors: list[str] = []

    name = form.get("name", "").strip()
    if not name:
        errors.append("Bitte einen Namen angeben.")

    direction = form.get("direction", "expense")
    if direction not in recurring.DIRECTIONS:
        errors.append("Bitte Ausgabe, Einnahme oder Umbuchung wählen.")
        direction = "expense"

    interval = form.get("interval", "monthly")
    if interval not in recurring.INTERVALS:
        errors.append("Bitte monatlich oder jährlich wählen.")
        interval = "monthly"

    try:
        amount = parse_cents(form.get("amount", ""))
    except ValueError:
        amount = 0
        errors.append("Bitte einen gültigen Betrag angeben.")
    if amount <= 0:
        errors.append("Der Betrag muss größer als 0 sein.")

    account_id = _positive_id(form.get("account_id", ""))
    if account_id is None:
        errors.append("Bitte ein Konto auswählen.")

    to_account_value = form.get("to_account_id", "")
    to_account_id = _positive_id(to_account_value) if to_account_value else None
    if direction == "transfer":
        if to_account_id is None:
            errors.append("Bitte ein Zielkonto auswählen.")
        elif to_account_id == account_id:
            errors.append("Quell- und Zielkonto müssen unterschiedlich sein.")
    elif to_account_id is not None:
        errors.append("Ein Zielkonto darf nur bei der Art „Umbuchung“ angegeben werden.")

    category_value = form.get("category_id", "")
    category_id = (
        None
        if direction == "transfer"
        else (_positive_id(category_value) if category_value else None)
    )

    try:
        start_date = parse_date(form.get("start_date", ""), "start_date")
    except HTTPException:
        start_date = ""
        errors.append("Bitte ein gültiges Startdatum angeben.")

    values = {
        "name": name,
        "direction": direction,
        "interval": interval,
        "amount_cents": amount,
        "account_id": account_id,
        "to_account_id": to_account_id if direction == "transfer" else None,
        "category_id": category_id,
        "start_date": start_date,
        "counterparty": form.get("counterparty", "").strip(),
        "description": form.get("description", "").strip(),
        "active": 1 if form.get("active", "1") == "1" else 0,
    }
    return values, errors


async def create_recurring(request: Request) -> Response:
    form = await _form(request)
    values, errors = _recurring_values(form)
    if not errors:
        try:
            recurring.create_rule(values)
            recurring.generate_due()
        except recurring.RecurringError as exc:
            errors.append(str(exc))

    if errors:
        return _render(
            request,
            "recurring.html",
            {**_recurring_context(), "errors": errors, "form": form},
            status_code=400,
        )
    return _redirect(request, "ui/recurring")


def _recurring_edit_context(rule_id: int, form: dict | None = None) -> dict:
    rule = recurring.get_rule(rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Regel nicht gefunden")
    if form is None:
        form = {
            **rule,
            "amount": _amount_input(rule["amount_cents"]),
            "account_id": str(rule["account_id"]),
            "to_account_id": str(rule["to_account_id"]) if rule["to_account_id"] else "",
            "category_id": str(rule["category_id"]) if rule["category_id"] else "",
            "active": "1" if rule["active"] else "0",
        }
    return {**_recurring_context(), "rule": rule, "form": form}


def edit_recurring_page(request: Request):
    rule_id = path_id(request.path_params["rule_id"])
    return _render(request, "recurring_edit.html", _recurring_edit_context(rule_id))


async def update_recurring(request: Request) -> Response:
    rule_id = path_id(request.path_params["rule_id"])
    form = await _form(request)
    values, errors = _recurring_values(form)
    if recurring.get_rule(rule_id) is None:
        raise HTTPException(status_code=404, detail="Regel nicht gefunden")
    if not errors:
        try:
            recurring.update_rule(rule_id, values)
            recurring.generate_due()
        except recurring.RecurringError as exc:
            errors.append(str(exc))

    if errors:
        return _render(
            request,
            "recurring_edit.html",
            {**_recurring_edit_context(rule_id, form), "errors": errors},
            status_code=400,
        )
    return _redirect(request, "ui/recurring")


def delete_recurring(request: Request) -> Response:
    try:
        recurring.delete_rule(path_id(request.path_params["rule_id"]))
    except recurring.RecurringError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _redirect(request, "ui/recurring")


def _salary_context() -> dict:
    return {
        "rules": salary.list_rules(),
        "accounts": _account_options(),
        "categories": _income_categories(),
        "summary": salary.planned_summary(),
        "today": date.today().isoformat(),
        "form": {"name": "Monatsgehalt"},
    }


def salary_page(request: Request):
    return _render(request, "salary.html", _salary_context())


def _salary_values(form: dict[str, str]) -> tuple[dict, list[str]]:
    """Formularwerte einer Gehaltsregel validieren."""
    errors: list[str] = []

    name = form.get("name", "").strip()
    if not name:
        errors.append("Bitte einen Namen angeben.")

    try:
        amount = parse_cents(form.get("amount", ""))
    except ValueError:
        amount = 0
        errors.append("Bitte einen gültigen Betrag angeben.")
    if amount <= 0:
        errors.append("Der Betrag muss größer als 0 sein.")

    account_id = _positive_id(form.get("account_id", ""))
    if account_id is None:
        errors.append("Bitte ein Konto auswählen.")

    category_value = form.get("category_id", "")
    category_id = _positive_id(category_value) if category_value else None

    try:
        start_date = parse_date(form.get("start_date", ""), "start_date")
    except HTTPException:
        start_date = ""
        errors.append("Bitte ein gültiges Datum für die erste Auszahlung angeben.")

    values = {
        "name": name,
        "amount_cents": amount,
        "account_id": account_id,
        "category_id": category_id,
        "start_date": start_date,
        "counterparty": form.get("counterparty", "").strip(),
        "description": form.get("description", "").strip(),
        "active": 1 if form.get("active", "1") == "1" else 0,
    }
    return values, errors


async def create_salary(request: Request) -> Response:
    form = await _form(request)
    values, errors = _salary_values(form)
    if not errors:
        try:
            salary.create_rule(values)
            salary.generate_due()
        except salary.SalaryError as exc:
            errors.append(str(exc))

    if errors:
        return _render(
            request,
            "salary.html",
            {**_salary_context(), "errors": errors, "form": form},
            status_code=400,
        )
    return _redirect(request, "ui/salary")


def _salary_edit_context(rule_id: int, form: dict | None = None) -> dict:
    rule = salary.get_rule(rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Gehaltsregel nicht gefunden")
    if form is None:
        form = {
            **rule,
            "amount": _amount_input(rule["amount_cents"]),
            "account_id": str(rule["account_id"]),
            "category_id": str(rule["category_id"]) if rule["category_id"] else "",
            "active": "1" if rule["active"] else "0",
        }
    return {**_salary_context(), "rule": rule, "form": form}


def edit_salary_page(request: Request):
    rule_id = path_id(request.path_params["rule_id"])
    return _render(request, "salary_edit.html", _salary_edit_context(rule_id))


async def update_salary(request: Request) -> Response:
    rule_id = path_id(request.path_params["rule_id"])
    form = await _form(request)
    values, errors = _salary_values(form)
    if salary.get_rule(rule_id) is None:
        raise HTTPException(status_code=404, detail="Gehaltsregel nicht gefunden")
    if not errors:
        try:
            salary.update_rule(rule_id, values)
            salary.generate_due()
        except salary.SalaryError as exc:
            errors.append(str(exc))

    if errors:
        return _render(
            request,
            "salary_edit.html",
            {**_salary_edit_context(rule_id, form), "errors": errors},
            status_code=400,
        )
    return _redirect(request, "ui/salary")


def delete_salary(request: Request) -> Response:
    try:
        salary.delete_rule(path_id(request.path_params["rule_id"]))
    except salary.SalaryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _redirect(request, "ui/salary")


def _backups_context() -> dict:
    return {
        "backups": [
            {**item, "size": _format_size(item["size_bytes"])} for item in backup.list_backups()
        ]
    }


def _backup_error(request: Request, exc: Exception):
    return _render(
        request,
        "backups.html",
        {
            **_backups_context(),
            "errors": [f"Backup konnte nicht erstellt werden: {exc}"],
        },
        status_code=500,
    )


def backups_page(request: Request):
    return _render(request, "backups.html", _backups_context())


def create_backup(request: Request) -> Response:
    try:
        backup.create_backup()
    except (OSError, sqlite3.Error) as exc:
        return _backup_error(request, exc)
    return _redirect(request, "ui/backups")


def download_current_backup(request: Request) -> Response:
    """Aktuelle Datenbank einmalig herunterladen, ohne sie zu speichern."""
    try:
        path = backup.create_backup()
    except (OSError, sqlite3.Error) as exc:
        return _backup_error(request, exc)
    return FileResponse(
        path,
        media_type="application/x-sqlite3",
        filename=path.name,
        background=BackgroundTask(lambda: path.unlink(missing_ok=True)),
    )


def download_backup(request: Request) -> Response:
    name = request.path_params["name"]
    path = backup.backup_path(name)
    if path is None:
        raise HTTPException(status_code=404, detail="Backup nicht gefunden")
    return FileResponse(path, media_type="application/x-sqlite3", filename=name)


def delete_backup(request: Request) -> Response:
    if not backup.delete_backup(request.path_params["name"]):
        raise HTTPException(status_code=404, detail="Backup nicht gefunden")
    return _redirect(request, "ui/backups")


routes = [
    Route("/", dashboard, methods=["GET"]),
    Route("/ui/transactions", transactions_page, methods=["GET"]),
    Route("/ui/transactions", create_transaction, methods=["POST"]),
    Route("/ui/transactions/{transaction_id}/delete", delete_transaction, methods=["POST"]),
    Route("/ui/transactions/{transaction_id}/edit", edit_transaction_page, methods=["GET"]),
    Route("/ui/transactions/{transaction_id}", update_transaction, methods=["POST"]),
    Route("/ui/transfers", transfers_page, methods=["GET"]),
    Route("/ui/transfers", create_transfer, methods=["POST"]),
    Route("/ui/transfers/{transfer_id}/edit", edit_transfer_page, methods=["GET"]),
    Route("/ui/transfers/{transfer_id}", update_transfer, methods=["POST"]),
    Route("/ui/transfers/{transfer_id}/delete", delete_transfer, methods=["POST"]),
    Route("/ui/accounts", accounts_page, methods=["GET"]),
    Route("/ui/accounts", create_account, methods=["POST"]),
    Route("/ui/accounts/{account_id}/delete", delete_account, methods=["POST"]),
    Route("/ui/accounts/{account_id}/edit", edit_account_page, methods=["GET"]),
    Route("/ui/accounts/{account_id}", update_account, methods=["POST"]),
    Route("/ui/categories", categories_page, methods=["GET"]),
    Route("/ui/categories", create_category, methods=["POST"]),
    Route("/ui/categories/{category_id}/delete", delete_category, methods=["POST"]),
    Route("/ui/reports", reports_page, methods=["GET"]),
    Route("/ui/budgets", budgets_page, methods=["GET"]),
    Route("/ui/budgets", create_budget, methods=["POST"]),
    Route("/ui/budgets/{budget_id}", update_budget, methods=["POST"]),
    Route("/ui/budgets/{budget_id}/delete", delete_budget, methods=["POST"]),
    Route("/ui/recurring", recurring_page, methods=["GET"]),
    Route("/ui/recurring", create_recurring, methods=["POST"]),
    Route("/ui/recurring/{rule_id}/edit", edit_recurring_page, methods=["GET"]),
    Route("/ui/recurring/{rule_id}", update_recurring, methods=["POST"]),
    Route("/ui/recurring/{rule_id}/delete", delete_recurring, methods=["POST"]),
    Route("/ui/salary", salary_page, methods=["GET"]),
    Route("/ui/salary", create_salary, methods=["POST"]),
    Route("/ui/salary/{rule_id}/edit", edit_salary_page, methods=["GET"]),
    Route("/ui/salary/{rule_id}", update_salary, methods=["POST"]),
    Route("/ui/salary/{rule_id}/delete", delete_salary, methods=["POST"]),
    Route("/ui/backups", backups_page, methods=["GET"]),
    Route("/ui/backups", create_backup, methods=["POST"]),
    Route("/ui/backups/download", download_current_backup, methods=["GET"]),
    Route("/ui/backups/{name}/download", download_backup, methods=["GET"]),
    Route("/ui/backups/{name}/delete", delete_backup, methods=["POST"]),
]
