export type StatementSummary = {
  statement_id: string;
  source_file: string;
  page_count: number;
  bank_id: string | null;
  bank_name: string | null;
  extraction_quality_score: number | null;
  extraction_quality_status: string | null;
  extraction_mode: string | null;
  period_start: string | null;
  period_end: string | null;
  coverage_status: string;
  coverage_pct: number | null;
  integrity_score: number | null;
  integrity_status: string | null;
  reconciliation_status: string | null;
  reconciliation_variance: string | null;
  transaction_count: number;
  credit_anchor: string | null;
  credit_anchor_method: string | null;
};

export type ClassifiedTransaction = {
  transaction_id: string;
  statement_id: string;
  source_file: string;
  source_page: number | null;
  date: string;
  description: string;
  amount: number;
  direction: string;
  category: string;
  classification_source: string;
  classification_reason: string;
  classification_model: string | null;
  needs_review: boolean;
};

export type McaPosition = {
  lender: string;
  tier: string;
  payment_amount: number;
  frequency: string;
  monthly_payment: number;
  observed_payments: number;
  first_observed_date: string;
  last_observed_date: string;
};

export type RevenueBaseline = {
  average_monthly_true_revenue: number;
  months_used: string[];
  partial_months_excluded: string[];
  basis: string;
  warning: string | null;
};

export type DebtRatios = {
  average_monthly_true_revenue: number;
  total_monthly_debt_service: number;
  total_debt_ratio_pct: number;
  individual_ratios_pct: Record<string, number>;
};

export type UnderwritingFeatures = {
  gross_deposits: number;
  average_monthly_true_revenue: number;
  revenue_trend_pct: number;
  revenue_volatility_pct: number;
  average_deposit_count: number;
  revenue_concentration_pct: number;
  median_deposit: number;
  largest_deposit: number;
  returned_payment_count: number;
  mca_position_count: number;
  monthly_mca_debt_service: number;
  mca_burden_pct: number;
  revenue_coverage_ratio: number;
};

export type ScorecardResult = {
  policy_version: string;
  score: number;
  max_score: number;
  grade: string;
  risk_tier: string;
  revenue_advance_multiple: number;
  max_total_debt_burden_pct: number;
  hard_stop: boolean;
  hard_stop_reasons: string[];
  breakdown: Record<string, number>;
};

export type DecisionReadiness = {
  status: string;
  automated_offer_allowed: boolean;
  blocking_reasons: string[];
  review_reasons: string[];
  checks: Record<string, string>;
};

export type AuditManifest = {
  run_id: string;
  generated_at: string;
  engine_version: string;
  classifier_model: string;
  vision_model: string;
  enable_ocr: boolean;
  enable_vision_fallback: boolean;
  source_documents: Array<{
    source_file: string;
    sha256: string;
    statement_id: string;
    bank_id: string | null;
    page_count: number;
  }>;
};

export type CreditProfile = {
  source_file: string;
  sha256: string;
  owner_name: string | null;
  fico_score: number | null;
  total_high_credit: number | null;
  revolving_credit_utilization_pct: number | null;
  active_collections_count: number | null;
  total_collections_amount: number | null;
  bankruptcies_found: boolean | null;
  number_of_mortgages: number | null;
  mortgage_ltv_details: string | null;
  evidence: Record<string, string>;
  warnings: string[];
  model_name: string | null;
};

export type ReviewRecalculation = {
  categories_by_transaction: Record<string, string>;
  needs_review_by_transaction: Record<string, boolean>;
  monthly_true_revenue: Record<string, number>;
  revenue_baseline: RevenueBaseline;
  debt_ratios: DebtRatios;
  features: UnderwritingFeatures;
  remaining_review_count: number;
  override_audit: Array<{
    transaction_id: string;
    previous_category: string;
    new_category: string;
    reason: string;
  }>;
  readiness_status: string;
  automated_offer_allowed: boolean;
  readiness_checks: Record<string, string>;
};

export type FundingCapacity = {
  max_by_revenue: number;
  max_by_debt_capacity: number;
  policy_cap: number | null;
  recommended_advance: number;
  remaining_monthly_debt_capacity: number;
  affordable_daily_payment: number;
  projected_new_monthly_payment: number;
  projected_total_debt_ratio_pct: number;
  factor_rate: number;
  term_business_days: number;
};

export type StatementAnalysis = {
  statements: StatementSummary[];
  transactions: ClassifiedTransaction[];
  mca_positions: McaPosition[];
  monthly_true_revenue: Record<string, number>;
  revenue_baseline: RevenueBaseline | null;
  debt_ratios: DebtRatios | null;
  features: UnderwritingFeatures | null;
  decision_readiness: DecisionReadiness | null;
  audit_manifest: AuditManifest | null;
  skipped_duplicates: string[];
  warnings: string[];
};
