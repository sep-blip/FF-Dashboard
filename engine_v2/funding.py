from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FundingPolicy:
    revenue_multiple: float
    max_total_debt_burden_pct: float
    factor_rate: float
    term_business_days: int
    business_days_per_month: float = 21.0
    absolute_max_advance: float | None = None

    def validate(self) -> None:
        if self.revenue_multiple < 0:
            raise ValueError("revenue_multiple must be non-negative")
        if not 0 <= self.max_total_debt_burden_pct <= 100:
            raise ValueError("max_total_debt_burden_pct must be between 0 and 100")
        if self.factor_rate <= 0:
            raise ValueError("factor_rate must be positive")
        if self.term_business_days <= 0:
            raise ValueError("term_business_days must be positive")
        if self.business_days_per_month <= 0:
            raise ValueError("business_days_per_month must be positive")


@dataclass(frozen=True)
class FundingCapacity:
    max_by_revenue: float
    max_by_debt_capacity: float
    policy_cap: float | None
    recommended_advance: float
    remaining_monthly_debt_capacity: float
    affordable_daily_payment: float
    projected_new_monthly_payment: float
    projected_total_debt_ratio_pct: float
    factor_rate: float
    term_business_days: int


def calculate_funding_capacity(
    *,
    average_monthly_true_revenue: float,
    existing_monthly_debt_service: float,
    policy: FundingPolicy,
) -> FundingCapacity:
    """Calculate a deterministic funding ceiling from explicit policy inputs.

    No model or LLM chooses the amount. The final advance is the minimum of the
    revenue multiple, debt-service capacity, and optional absolute policy cap.
    """
    policy.validate()

    revenue = max(0.0, float(average_monthly_true_revenue))
    existing_debt = max(0.0, float(existing_monthly_debt_service))

    max_total_monthly_debt = revenue * (policy.max_total_debt_burden_pct / 100.0)
    remaining_monthly = max(0.0, max_total_monthly_debt - existing_debt)
    affordable_daily = remaining_monthly / policy.business_days_per_month

    # MCA payback = advance * factor. The daily payment is payback / term days.
    max_by_debt = (
        affordable_daily * policy.term_business_days / policy.factor_rate
        if policy.factor_rate > 0 else 0.0
    )
    max_by_revenue = revenue * policy.revenue_multiple

    ceilings = [max_by_revenue, max_by_debt]
    if policy.absolute_max_advance is not None:
        ceilings.append(max(0.0, float(policy.absolute_max_advance)))

    recommended = max(0.0, min(ceilings)) if ceilings else 0.0
    new_daily = (
        recommended * policy.factor_rate / policy.term_business_days
        if policy.term_business_days else 0.0
    )
    new_monthly = new_daily * policy.business_days_per_month
    projected_ratio = (
        (existing_debt + new_monthly) / revenue * 100.0
        if revenue > 0 else 0.0
    )

    return FundingCapacity(
        max_by_revenue=round(max_by_revenue, 2),
        max_by_debt_capacity=round(max_by_debt, 2),
        policy_cap=(
            round(float(policy.absolute_max_advance), 2)
            if policy.absolute_max_advance is not None else None
        ),
        recommended_advance=round(recommended, 2),
        remaining_monthly_debt_capacity=round(remaining_monthly, 2),
        affordable_daily_payment=round(affordable_daily, 2),
        projected_new_monthly_payment=round(new_monthly, 2),
        projected_total_debt_ratio_pct=round(projected_ratio, 2),
        factor_rate=policy.factor_rate,
        term_business_days=policy.term_business_days,
    )
