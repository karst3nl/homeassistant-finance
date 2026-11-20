"""Tests für die Cent-Arithmetik."""

from __future__ import annotations

from decimal import Decimal

import pytest
from money import cents_to_decimal, format_cents, parse_cents


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1234, 1234),
        ("1234", 123400),
        ("1234.56", 123456),
        ("1234,56", 123456),
        ("1.234,56", 123456),
        ("1,234.56", 123456),
        ("-42,31", -4231),
        ("+0,01", 1),
        ("0,1", 10),
        (" 42,00 € ", 4200),
    ],
)
def test_parse_cents(value: str | int, expected: int) -> None:
    assert parse_cents(value) == expected


@pytest.mark.parametrize("value", ["", "abc", "1.2.3", "12,34,56", "1,2345", True, None])
def test_parse_cents__lehnt_ungueltige_werte_ab(value: object) -> None:
    with pytest.raises(ValueError):
        parse_cents(value)  # type: ignore[arg-type]


def test_cent_arithmetik_ohne_rundungsfehler() -> None:
    assert parse_cents("0,1") + parse_cents("0,2") == 30


def test_cent_und_decimal() -> None:
    assert cents_to_decimal(123456) == Decimal("1234.56")
    assert format_cents(123456) == "1.234,56 EUR"
    assert format_cents(-4231) == "-42,31 EUR"
