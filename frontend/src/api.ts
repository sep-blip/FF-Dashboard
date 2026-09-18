import type {
  ClassifiedTransaction,
  CreditProfile,
  FundingCapacity,
  ReviewRecalculation,
  ScorecardResult,
  StatementAnalysis,
} from "./types";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

export async function analyzeStatements(
  files: File[],
  options: {
    enableOcr: boolean;
    enableVisionFallback: boolean;
    useAiClassifier: boolean;
  },
): Promise<StatementAnalysis> {
  const body = new FormData();
  for (const file of files) {
    body.append("files", file);
  }
  body.append("enable_ocr", String(options.enableOcr));
  body.append(
    "enable_vision_fallback",
    String(options.enableVisionFallback),
  );
  body.append("use_ai_classifier", String(options.useAiClassifier));

  const response = await fetch(
    `${API_BASE_URL}/v1/documents/bank-statements/analyze`,
    {
      method: "POST",
      body,
    },
  );

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(
      payload?.detail ||
        `Statement analysis failed with HTTP ${response.status}`,
    );
  }

  return response.json() as Promise<StatementAnalysis>;
}


export async function calculateFundingCapacity(input: {
  averageMonthlyTrueRevenue: number;
  existingMonthlyDebtService: number;
  revenueMultiple: number;
  maxTotalDebtBurdenPct: number;
  factorRate: number;
  termBusinessDays: number;
  absoluteMaxAdvance?: number | null;
}): Promise<FundingCapacity> {
  const response = await fetch(
    `${API_BASE_URL}/v1/underwriting/funding-capacity`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        average_monthly_true_revenue: input.averageMonthlyTrueRevenue,
        existing_monthly_debt_service: input.existingMonthlyDebtService,
        policy: {
          revenue_multiple: input.revenueMultiple,
          max_total_debt_burden_pct: input.maxTotalDebtBurdenPct,
          factor_rate: input.factorRate,
          term_business_days: input.termBusinessDays,
          absolute_max_advance: input.absoluteMaxAdvance ?? null,
        },
      }),
    },
  );

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(
      payload?.detail ||
        `Funding-capacity calculation failed with HTTP ${response.status}`,
    );
  }

  return response.json() as Promise<FundingCapacity>;
}


export async function recalculateReviewedTransactions(input: {
  transactions: ClassifiedTransaction[];
  overrides: Array<{
    transactionId: string;
    category: string;
    reason: string;
  }>;
  coverageStatusByMonth: Record<string, string>;
  monthlyDebtServiceByLender: Record<string, number>;
  readinessChecks: Record<string, string>;
}): Promise<ReviewRecalculation> {
  const response = await fetch(
    `${API_BASE_URL}/v1/underwriting/recalculate-reviewed-transactions`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        transactions: input.transactions.map((transaction) => ({
          transaction_id: transaction.transaction_id,
          date: transaction.date,
          amount: transaction.amount,
          direction: transaction.direction,
          category: transaction.category,
          needs_review: transaction.needs_review,
        })),
        overrides: input.overrides.map((override) => ({
          transaction_id: override.transactionId,
          category: override.category,
          reason: override.reason || "Underwriter override",
        })),
        coverage_status_by_month: input.coverageStatusByMonth,
        monthly_debt_service_by_lender:
          input.monthlyDebtServiceByLender,
        readiness_checks: input.readinessChecks,
      }),
    },
  );

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(
      payload?.detail ||
        `Review recalculation failed with HTTP ${response.status}`,
    );
  }

  return response.json() as Promise<ReviewRecalculation>;
}


export async function analyzeCreditReport(
  file: File,
  options: { enableOcr: boolean },
): Promise<CreditProfile> {
  const body = new FormData();
  body.append("file", file);
  body.append("enable_ocr", String(options.enableOcr));

  const response = await fetch(
    `${API_BASE_URL}/v1/documents/credit-report/analyze`,
    {
      method: "POST",
      body,
    },
  );

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(
      payload?.detail ||
        `Credit-report analysis failed with HTTP ${response.status}`,
    );
  }

  return response.json() as Promise<CreditProfile>;
}


export async function calculateScorecard(input: {
  averageMonthlyTrueRevenue: number;
  revenueTrendPct: number;
  averageDepositCount: number;
  revenueVolatilityPct: number;
  averageDailyBalance: number;
  mcaPositionCount: number;
  mcaBurdenPct: number;
  borrowingVelocity: string;
  returnedAchOrMissedPayments: number;
  negativeDays: number;
  timeInBusinessMonths: number;
  industryScore: number;
  seasonalityScore: number;
  creditScore: number;
  publicRecords: string;
  bankVerification: string;
  revenueConcentrationPct: number;
  suspectedFraud: boolean;
  severeWashTransactions: boolean;
  activeLenderDefault: boolean;
}): Promise<ScorecardResult> {
  const response = await fetch(
    `${API_BASE_URL}/v1/underwriting/scorecard`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        average_monthly_true_revenue: input.averageMonthlyTrueRevenue,
        revenue_trend_pct: input.revenueTrendPct,
        average_deposit_count: input.averageDepositCount,
        revenue_volatility_pct: input.revenueVolatilityPct,
        average_daily_balance: input.averageDailyBalance,
        mca_position_count: input.mcaPositionCount,
        mca_burden_pct: input.mcaBurdenPct,
        borrowing_velocity: input.borrowingVelocity,
        returned_ach_or_missed_payments:
          input.returnedAchOrMissedPayments,
        negative_days: input.negativeDays,
        time_in_business_months: input.timeInBusinessMonths,
        industry_score: input.industryScore,
        seasonality_score: input.seasonalityScore,
        credit_score: input.creditScore,
        public_records: input.publicRecords,
        bank_verification: input.bankVerification,
        revenue_concentration_pct: input.revenueConcentrationPct,
        suspected_fraud: input.suspectedFraud,
        severe_wash_transactions: input.severeWashTransactions,
        active_lender_default: input.activeLenderDefault,
      }),
    },
  );

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(
      payload?.detail ||
        `Scorecard calculation failed with HTTP ${response.status}`,
    );
  }

  return response.json() as Promise<ScorecardResult>;
}
