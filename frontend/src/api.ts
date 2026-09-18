import type { FundingCapacity, StatementAnalysis } from "./types";

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
