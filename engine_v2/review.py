from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from .constants import ALLOWED_CATEGORIES, REVIEW_REQUIRED
from .features import UnderwritingFeatures, calculate_underwriting_features
from .metrics import (
    DebtRatioMetrics,
    RevenueBaseline,
    calculate_debt_ratios,
    select_revenue_baseline,
)


@dataclass(frozen=True)
class ReviewedTransaction:
    transaction_id: str
    date: str
    description: str
    amount: float
    direction: str
    category: str
    needs_review: bool


@dataclass(frozen=True)
class TransactionOverride:
    transaction_id: str
    category: str
    reason: str


@dataclass(frozen=True)
class OverrideAuditEvent:
    transaction_id: str
    previous_category: str
    new_category: str
    reason: str


@dataclass
class ReviewRecalculation:
    categories_by_transaction: dict[str, str] = field(default_factory=dict)
    needs_review_by_transaction: dict[str, bool] = field(default_factory=dict)
    monthly_true_revenue: dict[str, float] = field(default_factory=dict)
    revenue_baseline: RevenueBaseline | None = None
    debt_ratios: DebtRatioMetrics | None = None
    features: UnderwritingFeatures | None = None
    remaining_review_count: int = 0
    override_audit: list[OverrideAuditEvent] = field(default_factory=list)
    readiness_status: str = "REVIEW_REQUIRED"
    automated_offer_allowed: bool = False
    readiness_checks: dict[str, str] = field(default_factory=dict)


def recalculate_after_review(
    *,
    transactions: list[ReviewedTransaction],
    overrides: list[TransactionOverride],
    coverage_status_by_month: Mapping[str, str],
    monthly_debt_service_by_lender: Mapping[str, float],
    readiness_checks: Mapping[str, str] | None = None,
    average_daily_balance: float = 0.0,
    negative_days: int = 0,
    balance_observed_days: int = 0,
) -> ReviewRecalculation:
    allowed = set(ALLOWED_CATEGORIES)
    by_id = {transaction.transaction_id: transaction for transaction in transactions}
    categories = {
        transaction.transaction_id: transaction.category
        for transaction in transactions
    }
    needs_review = {
        transaction.transaction_id: transaction.needs_review
        for transaction in transactions
    }

    audit: list[OverrideAuditEvent] = []
    seen_override_ids: set[str] = set()

    for override in overrides:
        if override.transaction_id in seen_override_ids:
            raise ValueError(
                f"Duplicate override for transaction {override.transaction_id}."
            )
        seen_override_ids.add(override.transaction_id)

        if override.category not in allowed:
            raise ValueError(
                f"Unsupported transaction category: {override.category}"
            )

        transaction = by_id.get(override.transaction_id)
        if transaction is None:
            raise ValueError(
                f"Override references unknown transaction "
                f"{override.transaction_id}."
            )
        if transaction.direction != "credit":
            raise ValueError(
                "Manual revenue classification overrides are allowed only "
                "for credit transactions."
            )

        previous = categories[override.transaction_id]
        categories[override.transaction_id] = override.category
        needs_review[override.transaction_id] = (
            override.category == REVIEW_REQUIRED
        )
        audit.append(
            OverrideAuditEvent(
                transaction_id=override.transaction_id,
                previous_category=previous,
                new_category=override.category,
                reason=override.reason.strip() or "Underwriter override",
            )
        )

    monthly: dict[str, float] = {}
    for transaction in transactions:
        category = categories[transaction.transaction_id]
        if (
            transaction.direction == "credit"
            and category.startswith("True Revenue")
        ):
            month = transaction.date[:7]
            monthly[month] = (
                monthly.get(month, 0.0) + float(transaction.amount)
            )

    monthly = {
        month: round(amount, 2)
        for month, amount in sorted(monthly.items())
    }

    baseline = select_revenue_baseline(
        monthly_true_revenue=monthly,
        coverage_status_by_month=coverage_status_by_month,
    )
    debt_ratios = calculate_debt_ratios(
        average_monthly_true_revenue=(
            baseline.average_monthly_true_revenue
        ),
        monthly_debt_service_by_lender=monthly_debt_service_by_lender,
    )

    adjusted_transactions = [
        ReviewedTransaction(
            transaction_id=transaction.transaction_id,
            date=transaction.date,
            description=transaction.description,
            amount=transaction.amount,
            direction=transaction.direction,
            category=categories[transaction.transaction_id],
            needs_review=needs_review[transaction.transaction_id],
        )
        for transaction in transactions
    ]
    features = calculate_underwriting_features(
        transactions=adjusted_transactions,
        monthly_true_revenue=monthly,
        baseline_months=baseline.months_used,
        average_monthly_true_revenue=(
            baseline.average_monthly_true_revenue
        ),
        mca_position_count=len(monthly_debt_service_by_lender),
        monthly_mca_debt_service=(
            debt_ratios.total_monthly_debt_service
        ),
        average_daily_balance=average_daily_balance,
        negative_days=negative_days,
        balance_observed_days=balance_observed_days,
    )

    remaining = sum(
        1
        for transaction in transactions
        if transaction.direction == "credit"
        and needs_review[transaction.transaction_id]
    )

    checks = dict(readiness_checks or {})
    checks["classification"] = "REVIEW" if remaining else "PASS"

    if any(value == "FAIL" for value in checks.values()):
        readiness_status = "BLOCKED"
        automated_offer_allowed = False
    elif any(value == "REVIEW" for value in checks.values()):
        readiness_status = "REVIEW_REQUIRED"
        automated_offer_allowed = False
    else:
        readiness_status = "READY"
        automated_offer_allowed = True

    return ReviewRecalculation(
        categories_by_transaction=categories,
        needs_review_by_transaction=needs_review,
        monthly_true_revenue=monthly,
        revenue_baseline=baseline,
        debt_ratios=debt_ratios,
        features=features,
        remaining_review_count=remaining,
        override_audit=audit,
        readiness_status=readiness_status,
        automated_offer_allowed=automated_offer_allowed,
        readiness_checks=checks,
    )
