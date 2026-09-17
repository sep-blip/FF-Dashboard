from __future__ import annotations

import calendar
from datetime import date
from typing import Iterable

from .models import CoverageStatus, StatementCoverage


def _inclusive_days(start: date, end: date) -> int:
    if end < start:
        raise ValueError("period_end cannot be earlier than period_start")
    return (end - start).days + 1


def calculate_statement_coverage(
    *,
    statement_id: str,
    period_start: date,
    period_end: date,
    transaction_dates: Iterable[date],
) -> StatementCoverage:
    """Measure observed statement coverage without rejecting partial months.

    For a single calendar month, expected_days is the number of days in that
    month. For custom periods, expected_days is the inclusive period length.
    observed_days is based on the statement period itself, not the number of
    transaction-active days, because zero-activity days are still valid coverage.
    """

    if period_start.year == period_end.year and period_start.month == period_end.month:
        expected_days = calendar.monthrange(period_start.year, period_start.month)[1]
    else:
        expected_days = _inclusive_days(period_start, period_end)

    observed_days = _inclusive_days(period_start, period_end)
    observed_days = min(observed_days, expected_days)

    coverage_pct = round((observed_days / expected_days) * 100, 2)
    if coverage_pct >= 99.5:
        status = CoverageStatus.COMPLETE
        warning = None
    else:
        status = CoverageStatus.PARTIAL
        warning = (
            f"Partial statement coverage: {observed_days}/{expected_days} days "
            f"({coverage_pct:.2f}%). Calculations may proceed, but projected "
            "monthly values must be identified as estimates."
        )

    # Materialize the iterable to surface obviously malformed future dates in a
    # later validation layer without using activity-day count as coverage.
    list(transaction_dates)

    return StatementCoverage(
        statement_id=statement_id,
        period_start=period_start,
        period_end=period_end,
        expected_days=expected_days,
        observed_days=observed_days,
        coverage_pct=coverage_pct,
        status=status,
        warning=warning,
    )
