from datetime import date
from decimal import Decimal

from engine_v2.statement_parser import (
    extract_credit_anchor,
    extract_opening_closing_balance,
    money_from_words,
    parse_date_from_line,
    parse_money_token,
)


def test_money_parser_handles_commas_and_parentheses():
    assert parse_money_token("$1,234.56") == Decimal("1234.56")
    assert parse_money_token("(1,234.56)") == Decimal("-1234.56")


def test_money_from_split_words():
    assert money_from_words(["1,234", ".56"]) == Decimal("1234.56")


def test_date_parser_uses_default_year():
    parsed, month = parse_date_from_line("17 Sep STRIPE", 2026)
    assert parsed == date(2026, 9, 17)
    assert month == "2026-09"


def test_opening_closing_balance_extraction():
    opening, closing = extract_opening_closing_balance(
        "Opening balance $10,000.00\nClosing balance = $12,345.67"
    )
    assert opening == Decimal("10000.00")
    assert closing == Decimal("12345.67")


def test_explicit_credit_anchor():
    anchor, method = extract_credit_anchor(
        "Total deposits & credits (12) + 45,678.90"
    )
    assert anchor == Decimal("45678.90")
    assert "RBC" in method
