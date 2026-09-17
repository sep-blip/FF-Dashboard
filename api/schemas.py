from __future__ import annotations

from pydantic import BaseModel, Field


class FundingPolicyRequest(BaseModel):
    revenue_multiple: float = Field(ge=0)
    max_total_debt_burden_pct: float = Field(ge=0, le=100)
    factor_rate: float = Field(gt=0)
    term_business_days: int = Field(gt=0)
    business_days_per_month: float = Field(default=21.0, gt=0)
    absolute_max_advance: float | None = Field(default=None, ge=0)


class FundingCapacityRequest(BaseModel):
    average_monthly_true_revenue: float = Field(ge=0)
    existing_monthly_debt_service: float = Field(ge=0)
    policy: FundingPolicyRequest


class FundingCapacityResponse(BaseModel):
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


class RevenueBaselineRequest(BaseModel):
    monthly_true_revenue: dict[str, float]
    coverage_status_by_month: dict[str, str] = Field(default_factory=dict)


class RevenueBaselineResponse(BaseModel):
    average_monthly_true_revenue: float
    months_used: list[str]
    partial_months_excluded: list[str]
    basis: str
    warning: str | None = None


class HealthResponse(BaseModel):
    status: str
    service: str
