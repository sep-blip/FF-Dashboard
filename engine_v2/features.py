from __future__ import annotations

import re
from dataclasses import dataclass
from statistics import median, stdev
from typing import Iterable


RETURNED_PAYMENT_PATTERN = re.compile(
    r"\bNSF\b|RETURNED\s+ITEM|ITEM\s+RETURNED|"
    r"\bUNPAID\b|DISHONOURED|FRAIS\s+EFFET\s+RET",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class UnderwritingFeatures:
    gross_deposits: float
    average_monthly_true_revenue: float
    revenue_trend_pct: float
    revenue_volatility_pct: float
    average_deposit_count: int
    revenue_concentration_pct: float
    median_deposit: float
    largest_deposit: float
    returned_payment_count: int
    average_daily_balance: float
    negative_days: int
    balance_observed_days: int
    mca_position_count: int
    monthly_mca_debt_service: float
    mca_burden_pct: float
    revenue_coverage_ratio: float


def calculate_underwriting_features(
    *,
    transactions: Iterable,
    monthly_true_revenue: dict[str, float],
    baseline_months: Iterable[str],
    average_monthly_true_revenue: float,
    mca_position_count: int,
    monthly_mca_debt_service: float,
    average_daily_balance: float = 0.0,
    negative_days: int = 0,
    balance_observed_days: int = 0,
) -> UnderwritingFeatures:
    transactions = list(transactions)
    credits = [
        transaction
        for transaction in transactions
        if transaction.direction == "credit"
    ]
    true_revenue = [
        transaction
        for transaction in credits
        if transaction.category.startswith("True Revenue")
    ]

    gross_deposits = sum(float(transaction.amount) for transaction in credits)
    credit_amounts = [float(transaction.amount) for transaction in credits]

    selected_months = [
        month
        for month in baseline_months
        if month in monthly_true_revenue
    ]
    if not selected_months:
        selected_months = sorted(monthly_true_revenue)

    selected_revenues = [
        float(monthly_true_revenue[month])
        for month in selected_months
    ]

    if len(selected_revenues) >= 2 and selected_revenues[0] > 0:
        revenue_trend_pct = (
            (selected_revenues[-1] - selected_revenues[0])
            / selected_revenues[0]
            * 100
        )
    else:
        revenue_trend_pct = 0.0

    if len(selected_revenues) >= 2 and average_monthly_true_revenue > 0:
        revenue_volatility_pct = (
            stdev(selected_revenues)
            / average_monthly_true_revenue
            * 100
        )
    else:
        revenue_volatility_pct = 0.0

    deposit_count_by_month: dict[str, int] = {}
    payer_totals: dict[str, float] = {}
    total_true_revenue = 0.0

    for transaction in true_revenue:
        month = transaction.date[:7]
        deposit_count_by_month[month] = (
            deposit_count_by_month.get(month, 0) + 1
        )
        payer = transaction.description.strip().upper() or "UNKNOWN"
        payer_totals[payer] = (
            payer_totals.get(payer, 0.0) + float(transaction.amount)
        )
        total_true_revenue += float(transaction.amount)

    count_months = selected_months or sorted(deposit_count_by_month)
    counts = [
        deposit_count_by_month.get(month, 0)
        for month in count_months
    ]
    average_deposit_count = (
        round(sum(counts) / len(counts))
        if counts else 0
    )

    top_payer = max(payer_totals.values()) if payer_totals else 0.0
    revenue_concentration_pct = (
        top_payer / total_true_revenue * 100
        if total_true_revenue > 0 else 0.0
    )

    returned_payment_count = sum(
        1
        for transaction in transactions
        if transaction.direction == "debit"
        and RETURNED_PAYMENT_PATTERN.search(transaction.description)
    )

    mca_burden_pct = (
        monthly_mca_debt_service
        / average_monthly_true_revenue
        * 100
        if average_monthly_true_revenue > 0
        else 0.0
    )
    revenue_coverage_ratio = (
        average_monthly_true_revenue / monthly_mca_debt_service
        if monthly_mca_debt_service > 0
        else 99.9
    )

    return UnderwritingFeatures(
        gross_deposits=round(gross_deposits, 2),
        average_monthly_true_revenue=round(
            average_monthly_true_revenue,
            2,
        ),
        revenue_trend_pct=round(revenue_trend_pct, 2),
        revenue_volatility_pct=round(revenue_volatility_pct, 2),
        average_deposit_count=int(average_deposit_count),
        revenue_concentration_pct=round(
            revenue_concentration_pct,
            2,
        ),
        median_deposit=round(
            median(credit_amounts) if credit_amounts else 0.0,
            2,
        ),
        largest_deposit=round(
            max(credit_amounts) if credit_amounts else 0.0,
            2,
        ),
        returned_payment_count=returned_payment_count,
        average_daily_balance=round(float(average_daily_balance), 2),
        negative_days=int(negative_days),
        balance_observed_days=int(balance_observed_days),
        mca_position_count=int(mca_position_count),
        monthly_mca_debt_service=round(
            monthly_mca_debt_service,
            2,
        ),
        mca_burden_pct=round(mca_burden_pct, 2),
        revenue_coverage_ratio=round(revenue_coverage_ratio, 2),
    )
