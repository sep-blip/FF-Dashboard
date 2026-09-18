export type StatementSummary = {
  statement_id: string;
  source_file: string;
  page_count: number;
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

export type StatementAnalysis = {
  statements: StatementSummary[];
  transactions: ClassifiedTransaction[];
  mca_positions: McaPosition[];
  monthly_true_revenue: Record<string, number>;
  revenue_baseline: RevenueBaseline | null;
  debt_ratios: DebtRatios | null;
  skipped_duplicates: string[];
  warnings: string[];
};
