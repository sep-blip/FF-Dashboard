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
    bank_id: str | None = None
    bank_name: str | None = None
    extraction_quality_score: int | None = None
    extraction_quality_status: str | None = None
    extraction_mode: str | None = None
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


class UnderwritingFeaturesResponse(BaseModel):
    gross_deposits: float
    average_monthly_true_revenue: float
    revenue_trend_pct: float
    revenue_volatility_pct: float
    average_deposit_count: int
    revenue_concentration_pct: float
    median_deposit: float
    largest_deposit: float
    returned_payment_count: int
    mca_position_count: int
    monthly_mca_debt_service: float
    mca_burden_pct: float
    revenue_coverage_ratio: float


class DecisionReadinessResponse(BaseModel):
    status: str
    automated_offer_allowed: bool
    blocking_reasons: list[str] = Field(default_factory=list)
    review_reasons: list[str] = Field(default_factory=list)
    checks: dict[str, str] = Field(default_factory=dict)


class SourceDocumentAuditResponse(BaseModel):
    source_file: str
    sha256: str
    statement_id: str
    bank_id: str | None = None
    page_count: int


class AuditManifestResponse(BaseModel):
    run_id: str
    generated_at: str
    engine_version: str
    classifier_model: str
    vision_model: str
    enable_ocr: bool
    enable_vision_fallback: bool
    source_documents: list[SourceDocumentAuditResponse]


class StatementAnalysisResponse(BaseModel):
    statements: list[StatementSummaryResponse]
    transactions: list[ClassifiedTransactionResponse]
    mca_positions: list[McaPositionResponse]
    monthly_true_revenue: dict[str, float]
    revenue_baseline: RevenueBaselineResponse | None = None
    debt_ratios: DebtRatioResponse | None = None
    features: UnderwritingFeaturesResponse | None = None
    decision_readiness: DecisionReadinessResponse | None = None
    audit_manifest: AuditManifestResponse | None = None
    skipped_duplicates: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)



class ReviewedTransactionRequest(BaseModel):
    transaction_id: str
    date: str
    description: str
    amount: float = Field(ge=0)
    direction: str
    category: str
    needs_review: bool


class TransactionOverrideRequest(BaseModel):
    transaction_id: str
    category: str
    reason: str = Field(default="Underwriter override", max_length=500)


class ReviewRecalculationRequest(BaseModel):
    transactions: list[ReviewedTransactionRequest]
    overrides: list[TransactionOverrideRequest] = Field(default_factory=list)
    coverage_status_by_month: dict[str, str] = Field(default_factory=dict)
    monthly_debt_service_by_lender: dict[str, float] = Field(default_factory=dict)
    readiness_checks: dict[str, str] = Field(default_factory=dict)


class OverrideAuditResponse(BaseModel):
    transaction_id: str
    previous_category: str
    new_category: str
    reason: str


class ReviewRecalculationResponse(BaseModel):
    categories_by_transaction: dict[str, str]
    needs_review_by_transaction: dict[str, bool]
    monthly_true_revenue: dict[str, float]
    revenue_baseline: RevenueBaselineResponse
    debt_ratios: DebtRatioResponse
    features: UnderwritingFeaturesResponse
    remaining_review_count: int
    override_audit: list[OverrideAuditResponse]
    readiness_status: str
    automated_offer_allowed: bool
    readiness_checks: dict[str, str]


class CreditProfileResponse(BaseModel):
    source_file: str
    sha256: str
    owner_name: str | None = None
    fico_score: int | None = None
    total_high_credit: float | None = None
    revolving_credit_utilization_pct: float | None = None
    active_collections_count: int | None = None
    total_collections_amount: float | None = None
    bankruptcies_found: bool | None = None
    number_of_mortgages: int | None = None
    mortgage_ltv_details: str | None = None
    evidence: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    model_name: str | None = None


class ScorecardRequest(BaseModel):
    average_monthly_true_revenue: float = Field(ge=0)
    revenue_trend_pct: float
    average_deposit_count: int = Field(ge=0)
    revenue_volatility_pct: float = Field(ge=0)
    average_daily_balance: float = Field(ge=0)
    mca_position_count: int = Field(ge=0)
    mca_burden_pct: float = Field(ge=0)
    borrowing_velocity: str
    returned_ach_or_missed_payments: int = Field(ge=0)
    negative_days: int = Field(ge=0)
    time_in_business_months: int = Field(ge=0)
    industry_score: int
    seasonality_score: int
    credit_score: int = Field(ge=300, le=900)
    public_records: str
    bank_verification: str
    revenue_concentration_pct: float = Field(ge=0)
    suspected_fraud: bool = False
    severe_wash_transactions: bool = False
    active_lender_default: bool = False


class ScorecardResponse(BaseModel):
    policy_version: str
    score: int
    max_score: int
    grade: str
    risk_tier: str
    revenue_advance_multiple: float
    max_total_debt_burden_pct: float
    hard_stop: bool
    hard_stop_reasons: list[str]
    breakdown: dict[str, int]
