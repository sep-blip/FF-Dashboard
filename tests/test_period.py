from datetime import date

from engine_v2.period import extract_statement_period


def test_explicit_statement_period():
    result = extract_statement_period(
        "Statement Period: August 1, 2026 to August 31, 2026"
    )
    assert result.period_start == date(2026, 8, 1)
    assert result.period_end == date(2026, 8, 31)
    assert result.confidence > 0.8


def test_unknown_period_does_not_guess():
    result = extract_statement_period("Transactions and balances follow")
    assert result.period_start is None
    assert result.period_end is None
    assert result.warning
