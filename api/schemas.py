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


class StatementSummaryResponse(BaseModel):
    statement_id: str
    source_file: str
    page_count: int
    period_start: str | None = None
    period_end: str | None = None
    coverage_status: str
    coverage_pct: float | None = None
    integrity_score: int | None = None
    integrity_status: str | None = None
    reconciliation_status: str | None = None
    reconciliation_variance: str | None = None
    transaction_count: int
    credit_anchor: str | None = None
    credit_anchor_method: str | None = None


class ClassifiedTransactionResponse(BaseModel):
    transaction_id: str
    statement_id: str
    source_file: str
    source_page: int | None = None
    date: str
    description: str
    amount: float
    direction: str
    category: str
    classification_source: str
    classification_reason: str
    classification_model: str | None = None
    needs_review: bool


class McaPositionResponse(BaseModel):
    lender: str
    tier: str
    payment_amount: float
    frequency: str
    monthly_payment: float
    observed_payments: int
    first_observed_date: str
    last_observed_date: str


class DebtRatioResponse(BaseModel):
    average_monthly_true_revenue: float
    total_monthly_debt_service: float
    total_debt_ratio_pct: float
    individual_ratios_pct: dict[str, float]


class StatementAnalysisResponse(BaseModel):
    statements: list[StatementSummaryResponse]
    transactions: list[ClassifiedTransactionResponse]
    mca_positions: list[McaPositionResponse]
    monthly_true_revenue: dict[str, float]
    revenue_baseline: RevenueBaselineResponse | None = None
    debt_ratios: DebtRatioResponse | None = None
    skipped_duplicates: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ApplicationCreateRequest(BaseModel):
    legal_name: str = Field(min_length=1, max_length=300)
    dba_name: str | None = Field(default=None, max_length=300)
    industry_code: str | None = Field(default=None, max_length=100)
    requested_amount: float | None = Field(default=None, ge=0)
    requested_term_business_days: int | None = Field(default=None, gt=0)


class ApplicationCreateResponse(BaseModel):
    merchant_id: str
    application_id: str


class PersistedStatementAnalysisResponse(StatementAnalysisResponse):
    application_id: str
    persisted: bool = True
