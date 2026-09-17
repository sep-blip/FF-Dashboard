from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True)
class RevenueBaseline:
    average_monthly_true_revenue: float
    months_used: tuple[str, ...]
    partial_months_excluded: tuple[str, ...]
    basis: str
    warning: str | None = None


@dataclass(frozen=True)
class DebtRatioMetrics:
    average_monthly_true_revenue: float
    total_monthly_debt_service: float
    total_debt_ratio_pct: float
    individual_ratios_pct: dict[str, float]


def select_revenue_baseline(
    *,
    monthly_true_revenue: Mapping[str, float],
    coverage_status_by_month: Mapping[str, str] | None = None,
) -> RevenueBaseline:
    """Select the revenue baseline used for underwriting math.

    Complete months are preferred. Partial months remain in observed reporting
    but are excluded from the funding baseline whenever at least one verified
    complete month exists. Unknown coverage is never silently treated as
    complete.
    """
    ordered = dict(sorted((str(k), float(v)) for k, v in monthly_true_revenue.items()))
    if not ordered:
        return RevenueBaseline(
            average_monthly_true_revenue=0.0,
            months_used=(),
            partial_months_excluded=(),
            basis="NO_DATA",
            warning="No monthly true-revenue observations are available.",
        )

    statuses = {str(k): str(v).upper() for k, v in (coverage_status_by_month or {}).items()}
    complete = [m for m in ordered if statuses.get(m) == "COMPLETE"]
    partial = [m for m in ordered if statuses.get(m) == "PARTIAL"]

    if complete:
        values = [ordered[m] for m in complete]
        excluded = tuple(m for m in partial if m not in complete)
        return RevenueBaseline(
            average_monthly_true_revenue=sum(values) / len(values),
            months_used=tuple(complete),
            partial_months_excluded=excluded,
            basis="VERIFIED_COMPLETE_MONTHS",
            warning=(
                f"Excluded {len(excluded)} partial month(s) from the underwriting baseline."
                if excluded else None
            ),
        )

    values = list(ordered.values())
    return RevenueBaseline(
        average_monthly_true_revenue=sum(values) / len(values),
        months_used=tuple(ordered),
        partial_months_excluded=(),
        basis="OBSERVED_COVERAGE_UNVERIFIED",
        warning=(
            "No verified complete month was available. The baseline uses observed "
            "monthly totals and should require underwriter review before final funding."
        ),
    )


def project_partial_month(
    *,
    observed_true_revenue: float,
    observed_days: int,
    expected_days: int,
) -> float | None:
    """Return a clearly estimated run-rate projection for display only."""
    if observed_days <= 0 or expected_days <= 0 or observed_days > expected_days:
        return None
    return round(float(observed_true_revenue) * expected_days / observed_days, 2)


def calculate_debt_ratios(
    *,
    average_monthly_true_revenue: float,
    monthly_debt_service_by_lender: Mapping[str, float],
) -> DebtRatioMetrics:
    revenue = max(0.0, float(average_monthly_true_revenue))
    debt = {str(k): max(0.0, float(v)) for k, v in monthly_debt_service_by_lender.items()}
    total = sum(debt.values())

    if revenue <= 0:
        ratios = {lender: 0.0 for lender in debt}
        total_ratio = 0.0
    else:
        ratios = {lender: round(amount / revenue * 100, 2) for lender, amount in debt.items()}
        total_ratio = round(total / revenue * 100, 2)

    return DebtRatioMetrics(
        average_monthly_true_revenue=revenue,
        total_monthly_debt_service=round(total, 2),
        total_debt_ratio_pct=total_ratio,
        individual_ratios_pct=ratios,
    )
