from datetime import date

from engine_v2.coverage import calculate_statement_coverage
from engine_v2.models import CoverageStatus


def test_partial_month_is_allowed_but_warned():
    result = calculate_statement_coverage(
        statement_id="stmt-1",
        period_start=date(2026, 9, 1),
        period_end=date(2026, 9, 17),
        transaction_dates=[],
    )

    assert result.status == CoverageStatus.PARTIAL
    assert result.expected_days == 30
    assert result.observed_days == 17
    assert result.coverage_pct == 56.67
    assert result.warning


def test_complete_month_passes():
    result = calculate_statement_coverage(
        statement_id="stmt-2",
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 31),
        transaction_dates=[],
    )

    assert result.status == CoverageStatus.COMPLETE
    assert result.warning is None
