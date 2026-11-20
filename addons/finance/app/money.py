"""Geldwerte werden ausschließlich als ganzzahlige Cent verarbeitet.

Keine Fließkommazahlen, kein Runden: Eingaben mit mehr als zwei Nachkommastellen
werden abgelehnt. Das verhindert die klassischen 0,1+0,2-Fehler.
"""

from __future__ import annotations

import re
from decimal import Decimal

_AMOUNT_RE = re.compile(r"^(?P<integer>\d{1,3}(?:[.,]\d{3})+|\d+)(?P<decimal>[.,]\d{1,2})?$")

# 10 Milliarden Euro in Cent – begrenzt unsinnige Werte und Summenüberläufe.
MAX_CENTS = 10**12


def _bounded(value: int) -> int:
    if abs(value) > MAX_CENTS:
        raise ValueError("Betrag ist zu groß")
    return value


def parse_cents(value: str | int) -> int:
    """Betrag in Cent umwandeln.

    Akzeptiert z. B. 1234, 1234.56, '1234,56', '1.234,56' und '1,234.56'.
    Tausendergruppen müssen aus drei Ziffern bestehen; mehr als zwei
    Nachkommastellen werden abgelehnt statt gerundet.
    """
    if isinstance(value, bool):
        raise ValueError("Wahrheitswerte sind keine Beträge")
    if isinstance(value, int):
        return _bounded(value)
    if not isinstance(value, str):
        raise ValueError("Betrag muss eine Zahl oder ein String sein")

    text = value.strip().replace("€", "").replace("\u00a0", "").replace(" ", "")
    sign = -1 if text.startswith("-") else 1
    text = text.lstrip("+-")

    match = _AMOUNT_RE.fullmatch(text)
    if match is None:
        raise ValueError(f"Ungültiger Betrag: {value!r}")

    integer = re.sub(r"[.,]", "", match.group("integer"))
    decimal = match.group("decimal")
    normalized = integer + ("." + decimal[1:] if decimal else "")
    return sign * _bounded(int(Decimal(normalized) * 100))


def cents_to_decimal(cents: int) -> Decimal:
    """Cent-Wert als Dezimalzahl im Euro zurückgeben."""
    return Decimal(cents) / 100


def format_cents(cents: int, currency: str = "EUR") -> str:
    """Betrag für die Anzeige formatieren, z. B. '-1.234,56 €'."""
    amount = cents_to_decimal(abs(cents))
    formatted = f"{amount:,.2f}".replace(",", "\u00a7").replace(".", ",").replace("\u00a7", ".")
    prefix = "-" if cents < 0 else ""
    return f"{prefix}{formatted} {currency}"
