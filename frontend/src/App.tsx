import { useMemo, useState } from "react";
import {
  analyzeCreditReport,
  analyzeStatements,
  calculateFundingCapacity,
  calculateScorecard,
  recalculateReviewedTransactions,
} from "./api";
import type {
  ClassifiedTransaction,
  CreditProfile,
  FundingCapacity,
  ReviewRecalculation,
  ScorecardResult,
  StatementAnalysis,
} from "./types";

const money = new Intl.NumberFormat("en-CA", {
  style: "currency",
  currency: "CAD",
  maximumFractionDigits: 2,
});

const CATEGORY_OPTIONS = [
  "True Revenue - POS / Processor",
  "True Revenue - Verified Cash",
  "True Revenue - Customer Payment / Cheque",
  "True Revenue - B2B E-Transfer",
  "Non-Revenue - Own-Account / Internal Transfer",
  "Non-Revenue - MCA / Loan Proceeds",
  "Non-Revenue - Refund / Reversal / NSF",
  "Non-Revenue - Gov / Tax / Insurance Proceeds",
  "Non-Revenue - Shareholder / Investment",
  "Non-Revenue - Wash / Round-Trip Transfer",
  "Review Required - Unidentified / Unusual Deposit",
] as const;

type ManualOverride = {
  category: string;
  reason: string;
};

function StatusPill({ value }: { value: string | null }) {
  const normalized = (value || "UNKNOWN").toUpperCase();
  const tone =
    normalized.includes("READY") ||
    normalized.includes("PASS") ||
    normalized.includes("COMPLETE") ||
    normalized.includes("LOW_CONCERN") ||
    normalized === "HIGH"
      ? "good"
      : normalized.includes("FAIL") ||
          normalized.includes("BLOCK") ||
          normalized.includes("HIGH_REVIEW")
        ? "risk"
        : "warn";

  return <span className={`pill ${tone}`}>{value || "Unknown"}</span>;
}

function coverageStatusByMonth(
  analysis: StatementAnalysis,
): Record<string, string> {
  const statuses: Record<string, string[]> = {};

  for (const statement of analysis.statements) {
    if (!statement.period_start || !statement.period_end) continue;
    const startMonth = statement.period_start.slice(0, 7);
    const endMonth = statement.period_end.slice(0, 7);
    if (startMonth !== endMonth) continue;

    statuses[startMonth] ||= [];
    statuses[startMonth].push(statement.coverage_status || "UNKNOWN");
  }

  const result: Record<string, string> = {};
  for (const [month, values] of Object.entries(statuses)) {
    if (values.includes("PARTIAL")) {
      result[month] = "PARTIAL";
    } else if (values.includes("UNKNOWN")) {
      result[month] = "UNKNOWN";
    } else if (values.every((value) => value === "COMPLETE")) {
      result[month] = "COMPLETE";
    } else {
      result[month] = "UNKNOWN";
    }
  }
  return result;
}

function TransactionTable({
  transactions,
  overrides,
  onCategoryChange,
  onReasonChange,
}: {
  transactions: ClassifiedTransaction[];
  overrides: Record<string, ManualOverride>;
  onCategoryChange: (transaction: ClassifiedTransaction, category: string) => void;
  onReasonChange: (transaction: ClassifiedTransaction, reason: string) => void;
}) {
  const credits = transactions.filter((txn) => txn.direction === "credit");

  return (
    <div className="table-shell">
      <table>
        <thead>
          <tr>
            <th>Date</th>
            <th>Description</th>
            <th>Amount</th>
            <th>Classification</th>
            <th>Source</th>
            <th>Underwriter review</th>
          </tr>
        </thead>
        <tbody>
          {credits.map((txn) => {
            const pending = overrides[txn.transaction_id];
            return (
              <tr key={txn.transaction_id}>
                <td>{txn.date}</td>
                <td>
                  <strong>{txn.description}</strong>
                  <small>{txn.classification_reason}</small>
                  <small>
                    {txn.source_file}
                    {txn.source_page ? ` · page ${txn.source_page}` : ""}
                  </small>
                </td>
                <td>{money.format(txn.amount)}</td>
                <td>
                  <strong>{txn.category}</strong>
                  <small>{txn.classification_source}</small>
                </td>
                <td>
                  {txn.classification_model || txn.classification_source}
                </td>
                <td className="review-cell">
                  <select
                    value={pending?.category || txn.category}
                    onChange={(event) =>
                      onCategoryChange(txn, event.target.value)
                    }
                  >
                    {CATEGORY_OPTIONS.map((category) => (
                      <option value={category} key={category}>
                        {category}
                      </option>
                    ))}
                  </select>
                  <input
                    type="text"
                    placeholder="Override reason"
                    value={pending?.reason || ""}
                    onChange={(event) =>
                      onReasonChange(txn, event.target.value)
                    }
                  />
                  {txn.needs_review ? (
                    <span className="pill risk">Review required</span>
                  ) : (
                    <span className="pill good">Current classification clear</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default function App() {
  const [files, setFiles] = useState<File[]>([]);
  const [creditFile, setCreditFile] = useState<File | null>(null);
  const [creditProfile, setCreditProfile] = useState<CreditProfile | null>(null);
  const [creditWorking, setCreditWorking] = useState(false);
  const [creditError, setCreditError] = useState<string | null>(null);
  const [enableOcr, setEnableOcr] = useState(false);
  const [enableVision, setEnableVision] = useState(true);
  const [useAi, setUseAi] = useState(true);
  const [analysis, setAnalysis] = useState<StatementAnalysis | null>(null);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [reviewOverrides, setReviewOverrides] = useState<
    Record<string, ManualOverride>
  >({});
  const [reviewResult, setReviewResult] =
    useState<ReviewRecalculation | null>(null);
  const [reviewWorking, setReviewWorking] = useState(false);
  const [reviewError, setReviewError] = useState<string | null>(null);

  const [scorecardError, setScorecardError] = useState<string | null>(null);
  const [scorecardWorking, setScorecardWorking] = useState(false);
  const [scorecardResult, setScorecardResult] =
    useState<ScorecardResult | null>(null);
  const [averageDailyBalance, setAverageDailyBalance] = useState(0);
  const [negativeDays, setNegativeDays] = useState(0);
  const [timeInBusinessMonths, setTimeInBusinessMonths] = useState(24);
  const [industryScore, setIndustryScore] = useState(5);
  const [seasonalityScore, setSeasonalityScore] = useState(3);
  const [creditScoreInput, setCreditScoreInput] = useState(650);
  const [publicRecords, setPublicRecords] = useState("Clean");
  const [borrowingVelocity, setBorrowingVelocity] =
    useState("0 in 90 Days");
  const [bankVerification, setBankVerification] =
    useState("Original PDF");
  const [suspectedFraud, setSuspectedFraud] = useState(false);
  const [severeWash, setSevereWash] = useState(false);
  const [activeLenderDefault, setActiveLenderDefault] = useState(false);

  const [fundingError, setFundingError] = useState<string | null>(null);
  const [fundingResult, setFundingResult] =
    useState<FundingCapacity | null>(null);
  const [revenueMultiple, setRevenueMultiple] = useState(0.7);
  const [maxDebtBurdenPct, setMaxDebtBurdenPct] = useState(15);
  const [factorRate, setFactorRate] = useState(1.3);
  const [termBusinessDays, setTermBusinessDays] = useState(126);
  const [absoluteCap, setAbsoluteCap] = useState("");

  const effectiveTransactions = useMemo(() => {
    if (!analysis) return [];
    if (!reviewResult) return analysis.transactions;

    return analysis.transactions.map((transaction) => ({
      ...transaction,
      category:
        reviewResult.categories_by_transaction[transaction.transaction_id] ??
        transaction.category,
      needs_review:
        reviewResult.needs_review_by_transaction[transaction.transaction_id] ??
        transaction.needs_review,
    }));
  }, [analysis, reviewResult]);

  const effectiveBaseline =
    reviewResult?.revenue_baseline || analysis?.revenue_baseline || null;
  const effectiveDebtRatios =
    reviewResult?.debt_ratios || analysis?.debt_ratios || null;
  const effectiveFeatures =
    reviewResult?.features || analysis?.features || null;

  const reviewCount = useMemo(() => {
    if (reviewResult) return reviewResult.remaining_review_count;
    return effectiveTransactions.filter(
      (transaction) =>
        transaction.direction === "credit" && transaction.needs_review,
    ).length;
  }, [effectiveTransactions, reviewResult]);

  const readinessStatus =
    reviewResult?.readiness_status ||
    analysis?.decision_readiness?.status ||
    null;

  const automatedOfferAllowed =
    reviewResult?.automated_offer_allowed ??
    analysis?.decision_readiness?.automated_offer_allowed ??
    false;

  const readinessChecks =
    reviewResult?.readiness_checks ||
    analysis?.decision_readiness?.checks ||
    {};

  const readinessIssues = Object.entries(readinessChecks).filter(
    ([, status]) => status !== "PASS",
  );

  function downloadAnalysis() {
    if (!analysis) return;
    const exportPayload = {
      ...analysis,
      credit_profile: creditProfile,
      manual_review: reviewResult,
      pending_overrides: reviewOverrides,
      scorecard: scorecardResult,
      funding_scenario: fundingResult,
    };
    const blob = new Blob(
      [JSON.stringify(exportPayload, null, 2)],
      { type: "application/json" },
    );
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `underwriting-analysis-${new Date()
      .toISOString()
      .slice(0, 10)}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  async function runCreditAnalysis() {
    if (!creditFile) return;
    setCreditWorking(true);
    setCreditError(null);
    try {
      const profile = await analyzeCreditReport(creditFile, {
        enableOcr: true,
      });
      setCreditProfile(profile);
      if (profile.fico_score != null) {
        setCreditScoreInput(profile.fico_score);
      }
      if (profile.bankruptcies_found === true) {
        setPublicRecords("Severe");
      } else if ((profile.active_collections_count || 0) > 0) {
        setPublicRecords("Moderate");
      } else if (
        profile.bankruptcies_found === false &&
        profile.active_collections_count === 0
      ) {
        setPublicRecords("Clean");
      }
    } catch (err) {
      setCreditError(
        err instanceof Error
          ? err.message
          : "Credit-report analysis failed.",
      );
    } finally {
      setCreditWorking(false);
    }
  }

  async function runAnalysis() {
    if (!files.length) return;
    setWorking(true);
    setError(null);
    setReviewOverrides({});
    setReviewResult(null);
    setReviewError(null);
    setScorecardResult(null);
    setScorecardError(null);
    setFundingResult(null);
    setFundingError(null);

    try {
      const result = await analyzeStatements(files, {
        enableOcr,
        enableVisionFallback: enableVision,
        useAiClassifier: useAi,
      });
      setAnalysis(result);

      if (result.features) {
        setAverageDailyBalance(
          result.features.average_daily_balance,
        );
        setNegativeDays(result.features.negative_days);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed.");
    } finally {
      setWorking(false);
    }
  }

  function updateOverrideCategory(
    transaction: ClassifiedTransaction,
    category: string,
  ) {
    setReviewOverrides((current) => ({
      ...current,
      [transaction.transaction_id]: {
        category,
        reason:
          current[transaction.transaction_id]?.reason ||
          "Underwriter classification review",
      },
    }));
  }

  function updateOverrideReason(
    transaction: ClassifiedTransaction,
    reason: string,
  ) {
    setReviewOverrides((current) => ({
      ...current,
      [transaction.transaction_id]: {
        category:
          current[transaction.transaction_id]?.category ||
          transaction.category,
        reason,
      },
    }));
  }

  async function applyReviews() {
    if (!analysis) return;
    const entries = Object.entries(reviewOverrides);
    if (!entries.length) return;

    setReviewWorking(true);
    setReviewError(null);
    setFundingResult(null);

    try {
      const monthlyDebt = Object.fromEntries(
        analysis.mca_positions.map((position) => [
          position.lender,
          position.monthly_payment,
        ]),
      );

      const result = await recalculateReviewedTransactions({
        transactions: effectiveTransactions,
        overrides: entries.map(([transactionId, override]) => ({
          transactionId,
          category: override.category,
          reason: override.reason,
        })),
        coverageStatusByMonth: coverageStatusByMonth(analysis),
        monthlyDebtServiceByLender: monthlyDebt,
        readinessChecks,
        averageDailyBalance:
          analysis.features?.average_daily_balance || 0,
        negativeDays: analysis.features?.negative_days || 0,
        balanceObservedDays:
          analysis.features?.balance_observed_days || 0,
      });

      setReviewResult(result);
      setReviewOverrides({});
    } catch (err) {
      setReviewError(
        err instanceof Error
          ? err.message
          : "Could not apply underwriter reviews.",
      );
    } finally {
      setReviewWorking(false);
    }
  }

  async function runScorecard() {
    if (!effectiveFeatures) return;
    setScorecardWorking(true);
    setScorecardError(null);
    setFundingResult(null);

    try {
      const result = await calculateScorecard({
        averageMonthlyTrueRevenue:
          effectiveFeatures.average_monthly_true_revenue,
        revenueTrendPct: effectiveFeatures.revenue_trend_pct,
        averageDepositCount: effectiveFeatures.average_deposit_count,
        revenueVolatilityPct:
          effectiveFeatures.revenue_volatility_pct,
        averageDailyBalance,
        mcaPositionCount: effectiveFeatures.mca_position_count,
        mcaBurdenPct: effectiveFeatures.mca_burden_pct,
        borrowingVelocity,
        returnedAchOrMissedPayments:
          effectiveFeatures.returned_payment_count,
        negativeDays,
        timeInBusinessMonths,
        industryScore,
        seasonalityScore,
        creditScore: creditScoreInput,
        publicRecords,
        bankVerification,
        revenueConcentrationPct:
          effectiveFeatures.revenue_concentration_pct,
        suspectedFraud,
        severeWashTransactions: severeWash,
        activeLenderDefault,
      });
      setScorecardResult(result);
      setRevenueMultiple(result.revenue_advance_multiple);
      setMaxDebtBurdenPct(result.max_total_debt_burden_pct);
    } catch (err) {
      setScorecardError(
        err instanceof Error
          ? err.message
          : "Scorecard calculation failed.",
      );
    } finally {
      setScorecardWorking(false);
    }
  }

  async function runFundingScenario() {
    if (!effectiveBaseline) return;
    setFundingError(null);

    try {
      const cap = absoluteCap.trim()
        ? Number(absoluteCap)
        : null;

      setFundingResult(
        await calculateFundingCapacity({
          averageMonthlyTrueRevenue:
            effectiveBaseline.average_monthly_true_revenue,
          existingMonthlyDebtService:
            effectiveDebtRatios?.total_monthly_debt_service || 0,
          revenueMultiple,
          maxTotalDebtBurdenPct: maxDebtBurdenPct,
          factorRate,
          termBusinessDays,
          absoluteMaxAdvance: cap,
        }),
      );
    } catch (err) {
      setFundingError(
        err instanceof Error
          ? err.message
          : "Funding-capacity calculation failed.",
      );
    }
  }

  return (
    <main className="page">
      <header className="topbar">
        <div>
          <p className="eyebrow">Forward Funding</p>
          <h1>Underwriting Workbench</h1>
          <p className="subtle">
            Statement extraction, true-revenue review, debt detection,
            document integrity and deterministic offer structuring.
          </p>
        </div>
        <span className="environment">V2</span>
      </header>

      <section className="panel upload-panel">
        <div>
          <h2>Analyze bank statements</h2>
          <p className="subtle">
            Upload one or more PDFs. Duplicate files are removed before
            analysis.
          </p>
        </div>

        <div className="upload-grid">
          <label className="dropzone">
            <input
              type="file"
              accept="application/pdf"
              multiple
              onChange={(event) =>
                setFiles(Array.from(event.target.files || []))
              }
            />
            <strong>
              {files.length
                ? `${files.length} statement file(s) selected`
                : "Choose PDF bank statements"}
            </strong>
            <span>
              {files.map((file) => file.name).join(" • ") ||
                "Native positioned PDF extraction is attempted first."}
            </span>
          </label>

          <label className="dropzone">
            <input
              type="file"
              accept="application/pdf"
              onChange={(event) =>
                setCreditFile(event.target.files?.[0] || null)
              }
            />
            <strong>
              {creditFile
                ? creditFile.name
                : "Choose credit report PDF"}
            </strong>
            <span>
              Structured bureau extraction fails closed when a field is not
              explicitly supported by the report.
            </span>
          </label>
        </div>

        <div className="controls">
          <label>
            <input
              type="checkbox"
              checked={useAi}
              onChange={(event) => setUseAi(event.target.checked)}
            />
            AI classification for unresolved credits
          </label>
          <label>
            <input
              type="checkbox"
              checked={enableOcr}
              onChange={(event) => setEnableOcr(event.target.checked)}
            />
            Positioned OCR fallback
          </label>
          <label>
            <input
              type="checkbox"
              checked={enableVision}
              onChange={(event) => setEnableVision(event.target.checked)}
            />
            Vision fallback for unreadable pages
          </label>
          <button
            className="secondary-button"
            disabled={!creditFile || creditWorking}
            onClick={runCreditAnalysis}
          >
            {creditWorking ? "Reading credit…" : "Analyze credit report"}
          </button>
          <button
            disabled={!files.length || working}
            onClick={runAnalysis}
          >
            {working ? "Analyzing…" : "Run underwriting analysis"}
          </button>
        </div>

        {creditError && (
          <div className="alert risk-alert">{creditError}</div>
        )}
        {error && <div className="alert risk-alert">{error}</div>}
      </section>

      {analysis && (
        <>
          <section
            className={`panel readiness-card ${(
              readinessStatus || "review_required"
            ).toLowerCase()}`}
          >
            <div className="readiness-header">
              <div>
                <p className="eyebrow">Decision readiness</p>
                <h2>
                  {(readinessStatus || "REVIEW_REQUIRED").replaceAll("_", " ")}
                </h2>
              </div>
              <StatusPill value={readinessStatus} />
            </div>

            {!reviewResult &&
              analysis.decision_readiness?.blocking_reasons.map((reason) => (
                <div className="alert risk-alert" key={reason}>
                  {reason}
                </div>
              ))}

            {!reviewResult &&
              analysis.decision_readiness?.review_reasons.map((reason) => (
                <div className="alert warning-alert" key={reason}>
                  {reason}
                </div>
              ))}

            {reviewResult &&
              readinessIssues.map(([check, status]) => (
                <div
                  className={
                    status === "FAIL"
                      ? "alert risk-alert"
                      : "alert warning-alert"
                  }
                  key={check}
                >
                  {check.replaceAll("_", " ")}: {status}
                </div>
              ))}

            <div className="readiness-actions">
              <small>
                Automated final offer:{" "}
                {automatedOfferAllowed
                  ? "allowed"
                  : "not allowed until controls are cleared"}
              </small>
              <button className="secondary-button" onClick={downloadAnalysis}>
                Download analysis JSON
              </button>
            </div>
          </section>

          {creditProfile && (
            <section className="panel">
              <div className="section-heading-row">
                <div>
                  <p className="eyebrow">Bureau data</p>
                  <h2>{creditProfile.owner_name || "Credit profile"}</h2>
                  <p className="subtle">
                    {creditProfile.source_file} ·{" "}
                    {creditProfile.model_name || "structured extraction"}
                  </p>
                </div>
                <StatusPill
                  value={
                    creditProfile.warnings.length
                      ? "REVIEW"
                      : "EXTRACTED"
                  }
                />
              </div>

              {creditProfile.warnings.map((warning) => (
                <div className="alert warning-alert" key={warning}>
                  {warning}
                </div>
              ))}

              <div className="kpis credit-kpis">
                <article className="kpi">
                  <span>FICO / Beacon</span>
                  <strong>
                    {creditProfile.fico_score ?? "Not found"}
                  </strong>
                  <small>Explicit report value only</small>
                </article>
                <article className="kpi">
                  <span>Revolving utilization</span>
                  <strong>
                    {creditProfile.revolving_credit_utilization_pct != null
                      ? `${creditProfile.revolving_credit_utilization_pct.toFixed(1)}%`
                      : "Not found"}
                  </strong>
                  <small>Not inferred from balances</small>
                </article>
                <article className="kpi">
                  <span>Active collections</span>
                  <strong>
                    {creditProfile.active_collections_count ?? "Not found"}
                  </strong>
                  <small>
                    {creditProfile.total_collections_amount != null
                      ? money.format(
                          creditProfile.total_collections_amount,
                        )
                      : "Amount not found"}
                  </small>
                </article>
                <article className="kpi">
                  <span>Reported high credit</span>
                  <strong>
                    {creditProfile.total_high_credit != null
                      ? money.format(creditProfile.total_high_credit)
                      : "Not found"}
                  </strong>
                  <small>Explicit report field</small>
                </article>
              </div>

              <div className="credit-detail-grid">
                <span>
                  Bankruptcy / proposal
                  <strong>
                    {creditProfile.bankruptcies_found == null
                      ? "Not established"
                      : creditProfile.bankruptcies_found
                        ? "Found"
                        : "Not found"}
                  </strong>
                </span>
                <span>
                  Mortgage trades
                  <strong>
                    {creditProfile.number_of_mortgages ?? "Not found"}
                  </strong>
                </span>
                <span>
                  Mortgage / LTV
                  <strong>
                    {creditProfile.mortgage_ltv_details || "Not found"}
                  </strong>
                </span>
              </div>
            </section>
          )}

          {analysis.warnings.length > 0 && (
            <section className="panel">
              <h2>Review warnings</h2>
              <div className="warning-stack">
                {analysis.warnings.map((warning, index) => (
                  <div className="alert warning-alert" key={index}>
                    {warning}
                  </div>
                ))}
              </div>
            </section>
          )}

          <section className="kpis">
            <article className="kpi">
              <span>Avg. true revenue</span>
              <strong>
                {money.format(
                  effectiveBaseline?.average_monthly_true_revenue || 0,
                )}
              </strong>
              <small>{effectiveBaseline?.basis || "No baseline"}</small>
            </article>
            <article className="kpi">
              <span>Monthly debt service</span>
              <strong>
                {money.format(
                  effectiveDebtRatios?.total_monthly_debt_service || 0,
                )}
              </strong>
              <small>
                {analysis.mca_positions.length} detected position(s)
              </small>
            </article>
            <article className="kpi">
              <span>Total debt ratio</span>
              <strong>
                {(effectiveDebtRatios?.total_debt_ratio_pct || 0).toFixed(1)}%
              </strong>
              <small>Monthly consistent basis</small>
            </article>
            <article className="kpi">
              <span>Credits requiring review</span>
              <strong>{reviewCount}</strong>
              <small>Fail-closed classification</small>
            </article>
          </section>

          <section className="panel">
            <div className="section-heading-row">
              <div>
                <h2>Statement controls</h2>
                <p className="subtle">
                  Extraction confidence is based on observable controls,
                  not model self-confidence.
                </p>
              </div>
            </div>

            <div className="table-shell">
              <table>
                <thead>
                  <tr>
                    <th>File / Bank</th>
                    <th>Extraction</th>
                    <th>Period</th>
                    <th>Coverage</th>
                    <th>Integrity</th>
                    <th>Reconciliation</th>
                    <th>Transactions</th>
                  </tr>
                </thead>
                <tbody>
                  {analysis.statements.map((statement) => (
                    <tr key={statement.statement_id}>
                      <td>
                        <strong>{statement.source_file}</strong>
                        <small>
                          {statement.bank_name || "Bank not identified"}
                        </small>
                      </td>
                      <td>
                        <StatusPill
                          value={statement.extraction_quality_status}
                        />
                        <small>
                          {statement.extraction_quality_score ?? "—"}/100 ·{" "}
                          {statement.extraction_mode || "unknown mode"}
                        </small>
                      </td>
                      <td>
                        {statement.period_start || "?"} →{" "}
                        {statement.period_end || "?"}
                      </td>
                      <td>
                        <StatusPill value={statement.coverage_status} />
                      </td>
                      <td>
                        <StatusPill value={statement.integrity_status} />
                        <small>
                          {statement.integrity_score ?? "—"}/100
                        </small>
                      </td>
                      <td>
                        <StatusPill
                          value={statement.reconciliation_status}
                        />
                      </td>
                      <td>{statement.transaction_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="panel">
            <h2>Existing MCA positions</h2>
            {analysis.mca_positions.length ? (
              <div className="table-shell">
                <table>
                  <thead>
                    <tr>
                      <th>Lender</th>
                      <th>Tier</th>
                      <th>Payment</th>
                      <th>Frequency</th>
                      <th>Monthly equivalent</th>
                      <th>Observed</th>
                    </tr>
                  </thead>
                  <tbody>
                    {analysis.mca_positions.map((position) => (
                      <tr key={position.lender}>
                        <td>{position.lender}</td>
                        <td>{position.tier}</td>
                        <td>{money.format(position.payment_amount)}</td>
                        <td>{position.frequency}</td>
                        <td>{money.format(position.monthly_payment)}</td>
                        <td>{position.observed_payments}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="subtle">No known MCA positions detected.</p>
            )}
          </section>

          <section className="panel">
            <div className="section-heading-row">
              <div>
                <h2>True-revenue reconciliation</h2>
                <p className="subtle">
                  Every manual change is sent through the deterministic
                  recalculation endpoint and included in the downloaded audit
                  artifact.
                </p>
              </div>
              <button
                disabled={
                  !Object.keys(reviewOverrides).length || reviewWorking
                }
                onClick={applyReviews}
              >
                {reviewWorking
                  ? "Applying…"
                  : `Apply ${Object.keys(reviewOverrides).length} review(s)`}
              </button>
            </div>

            {reviewError && (
              <div className="alert risk-alert">{reviewError}</div>
            )}

            {reviewResult?.override_audit.length ? (
              <div className="alert good-alert">
                Applied {reviewResult.override_audit.length} underwriter
                override(s). Metrics and readiness were recalculated.
              </div>
            ) : null}

            <TransactionTable
              transactions={effectiveTransactions}
              overrides={reviewOverrides}
              onCategoryChange={updateOverrideCategory}
              onReasonChange={updateOverrideReason}
            />
          </section>

          <section className="panel">
            <div className="section-heading-row">
              <div>
                <h2>Risk scorecard</h2>
                <p className="subtle">
                  Automated cash-flow features are combined with bureau and
                  underwriter inputs. The scorecard is deterministic and
                  versioned.
                </p>
              </div>
              {scorecardResult && (
                <StatusPill
                  value={
                    scorecardResult.hard_stop
                      ? "HARD STOP"
                      : scorecardResult.grade
                  }
                />
              )}
            </div>

            {effectiveFeatures ? (
              <>
                <div className="kpis scorecard-feature-kpis">
                  <article className="kpi">
                    <span>Revenue trend</span>
                    <strong>
                      {effectiveFeatures.revenue_trend_pct.toFixed(1)}%
                    </strong>
                    <small>Selected underwriting months</small>
                  </article>
                  <article className="kpi">
                    <span>Revenue volatility</span>
                    <strong>
                      {effectiveFeatures.revenue_volatility_pct.toFixed(1)}%
                    </strong>
                    <small>Coefficient of variation</small>
                  </article>
                  <article className="kpi">
                    <span>MCA burden</span>
                    <strong>
                      {effectiveFeatures.mca_burden_pct.toFixed(1)}%
                    </strong>
                    <small>
                      {effectiveFeatures.mca_position_count} position(s)
                    </small>
                  </article>
                  <article className="kpi">
                    <span>Revenue concentration</span>
                    <strong>
                      {effectiveFeatures.revenue_concentration_pct.toFixed(1)}%
                    </strong>
                    <small>Largest identified payer share</small>
                  </article>
                </div>

                <div className="scorecard-grid">
                  <label>
                    Average daily balance
                    <input
                      type="number"
                      min="0"
                      step="100"
                      value={averageDailyBalance}
                      onChange={(event) =>
                        setAverageDailyBalance(Number(event.target.value))
                      }
                    />
                  </label>
                  <label>
                    Negative days
                    <input
                      type="number"
                      min="0"
                      step="1"
                      value={negativeDays}
                      onChange={(event) =>
                        setNegativeDays(Number(event.target.value))
                      }
                    />
                  </label>
                  <label>
                    Time in business (months)
                    <input
                      type="number"
                      min="0"
                      step="1"
                      value={timeInBusinessMonths}
                      onChange={(event) =>
                        setTimeInBusinessMonths(
                          Number(event.target.value),
                        )
                      }
                    />
                  </label>
                  <label>
                    Industry points (0-8)
                    <input
                      type="number"
                      min="0"
                      max="8"
                      step="1"
                      value={industryScore}
                      onChange={(event) =>
                        setIndustryScore(Number(event.target.value))
                      }
                    />
                  </label>
                  <label>
                    Seasonality points (0-6)
                    <input
                      type="number"
                      min="0"
                      max="6"
                      step="1"
                      value={seasonalityScore}
                      onChange={(event) =>
                        setSeasonalityScore(Number(event.target.value))
                      }
                    />
                  </label>
                  <label>
                    Credit score
                    <input
                      type="number"
                      min="300"
                      max="900"
                      step="1"
                      value={creditScoreInput}
                      onChange={(event) =>
                        setCreditScoreInput(Number(event.target.value))
                      }
                    />
                  </label>
                  <label>
                    Borrowing velocity
                    <select
                      value={borrowingVelocity}
                      onChange={(event) =>
                        setBorrowingVelocity(event.target.value)
                      }
                    >
                      <option>0 in 90 Days</option>
                      <option>1 in 90 Days</option>
                      <option>2+ in 90 Days</option>
                    </select>
                  </label>
                  <label>
                    Public records
                    <select
                      value={publicRecords}
                      onChange={(event) =>
                        setPublicRecords(event.target.value)
                      }
                    >
                      <option>Clean</option>
                      <option>Minor</option>
                      <option>Moderate</option>
                      <option>Severe</option>
                    </select>
                  </label>
                  <label>
                    Bank verification
                    <select
                      value={bankVerification}
                      onChange={(event) =>
                        setBankVerification(event.target.value)
                      }
                    >
                      <option>Bank Connect</option>
                      <option>Original PDF</option>
                      <option>Minor inconsistency</option>
                      <option>Unverified</option>
                    </select>
                  </label>
                </div>

                <div className="flag-grid">
                  <label>
                    <input
                      type="checkbox"
                      checked={suspectedFraud}
                      onChange={(event) =>
                        setSuspectedFraud(event.target.checked)
                      }
                    />
                    Suspected altered statements / fraud
                  </label>
                  <label>
                    <input
                      type="checkbox"
                      checked={severeWash}
                      onChange={(event) =>
                        setSevereWash(event.target.checked)
                      }
                    />
                    Severe wash transactions
                  </label>
                  <label>
                    <input
                      type="checkbox"
                      checked={activeLenderDefault}
                      onChange={(event) =>
                        setActiveLenderDefault(event.target.checked)
                      }
                    />
                    Active lender default / collections
                  </label>
                </div>

                <div className="scenario-inputs">
                  <span>
                    Returned ACH / missed payments:{" "}
                    <strong>
                      {effectiveFeatures.returned_payment_count}
                    </strong>
                  </span>
                  <span>
                    Avg. deposit count:{" "}
                    <strong>
                      {effectiveFeatures.average_deposit_count}
                    </strong>
                  </span>
                  <button
                    disabled={scorecardWorking}
                    onClick={runScorecard}
                  >
                    {scorecardWorking
                      ? "Scoring…"
                      : "Calculate scorecard"}
                  </button>
                </div>

                {scorecardError && (
                  <div className="alert risk-alert">
                    {scorecardError}
                  </div>
                )}

                {scorecardResult?.hard_stop && (
                  <div className="alert risk-alert">
                    Hard stop:{" "}
                    {scorecardResult.hard_stop_reasons.join("; ")}
                  </div>
                )}

                {scorecardResult && !scorecardResult.hard_stop && (
                  <>
                    <div className="kpis scorecard-results">
                      <article className="kpi">
                        <span>Score</span>
                        <strong>
                          {scorecardResult.score} /{" "}
                          {scorecardResult.max_score}
                        </strong>
                        <small>
                          {scorecardResult.policy_version}
                        </small>
                      </article>
                      <article className="kpi">
                        <span>Grade</span>
                        <strong>{scorecardResult.grade}</strong>
                        <small>{scorecardResult.risk_tier}</small>
                      </article>
                      <article className="kpi">
                        <span>Revenue advance multiple</span>
                        <strong>
                          {(
                            scorecardResult.revenue_advance_multiple *
                            100
                          ).toFixed(0)}
                          %
                        </strong>
                        <small>
                          Applied to funding scenario
                        </small>
                      </article>
                      <article className="kpi">
                        <span>Max total debt burden</span>
                        <strong>
                          {scorecardResult.max_total_debt_burden_pct.toFixed(
                            1,
                          )}
                          %
                        </strong>
                        <small>
                          Applied to funding scenario
                        </small>
                      </article>
                    </div>

                    <details className="score-breakdown">
                      <summary>Score breakdown</summary>
                      <div className="audit-grid">
                        {Object.entries(
                          scorecardResult.breakdown,
                        ).map(([component, points]) => (
                          <span key={component}>
                            {component.replaceAll("_", " ")}
                            <strong>{points} pts</strong>
                          </span>
                        ))}
                      </div>
                    </details>
                  </>
                )}
              </>
            ) : (
              <p className="subtle">
                Process bank statements before calculating the scorecard.
              </p>
            )}
          </section>

          <section className="panel">
            <div className="section-heading-row">
              <div>
                <h2>Funding capacity scenario</h2>
                <p className="subtle">
                  Deterministic scenario math. A scenario is not a final offer
                  unless decision readiness is READY.
                </p>
              </div>
              <StatusPill
                value={automatedOfferAllowed ? "READY" : "SCENARIO ONLY"}
              />
            </div>

            <div className="policy-grid">
              <label>
                Revenue multiple
                <input
                  type="number"
                  min="0"
                  step="0.05"
                  value={revenueMultiple}
                  onChange={(event) =>
                    setRevenueMultiple(Number(event.target.value))
                  }
                />
              </label>
              <label>
                Max total debt burden %
                <input
                  type="number"
                  min="0"
                  max="100"
                  step="0.5"
                  value={maxDebtBurdenPct}
                  onChange={(event) =>
                    setMaxDebtBurdenPct(Number(event.target.value))
                  }
                />
              </label>
              <label>
                Factor rate
                <input
                  type="number"
                  min="0.01"
                  step="0.01"
                  value={factorRate}
                  onChange={(event) =>
                    setFactorRate(Number(event.target.value))
                  }
                />
              </label>
              <label>
                Term business days
                <input
                  type="number"
                  min="1"
                  step="1"
                  value={termBusinessDays}
                  onChange={(event) =>
                    setTermBusinessDays(Number(event.target.value))
                  }
                />
              </label>
              <label>
                Absolute cap (optional)
                <input
                  type="number"
                  min="0"
                  step="1000"
                  placeholder="No cap"
                  value={absoluteCap}
                  onChange={(event) =>
                    setAbsoluteCap(event.target.value)
                  }
                />
              </label>
            </div>

            <div className="scenario-inputs">
              <span>
                Revenue baseline:{" "}
                <strong>
                  {money.format(
                    effectiveBaseline?.average_monthly_true_revenue || 0,
                  )}
                </strong>
              </span>
              <span>
                Existing monthly debt:{" "}
                <strong>
                  {money.format(
                    effectiveDebtRatios?.total_monthly_debt_service || 0,
                  )}
                </strong>
              </span>
              <button onClick={runFundingScenario}>
                Calculate scenario
              </button>
            </div>

            {fundingError && (
              <div className="alert risk-alert">{fundingError}</div>
            )}

            {fundingResult && (
              <div className="kpis scenario-results">
                <article className="kpi">
                  <span>Recommended advance</span>
                  <strong>
                    {money.format(fundingResult.recommended_advance)}
                  </strong>
                  <small>
                    Lowest applicable deterministic ceiling
                  </small>
                </article>
                <article className="kpi">
                  <span>Affordable daily payment</span>
                  <strong>
                    {money.format(fundingResult.affordable_daily_payment)}
                  </strong>
                  <small>
                    {fundingResult.term_business_days} business days
                  </small>
                </article>
                <article className="kpi">
                  <span>Projected monthly payment</span>
                  <strong>
                    {money.format(
                      fundingResult.projected_new_monthly_payment,
                    )}
                  </strong>
                  <small>New position only</small>
                </article>
                <article className="kpi">
                  <span>Projected total debt ratio</span>
                  <strong>
                    {fundingResult.projected_total_debt_ratio_pct.toFixed(1)}%
                  </strong>
                  <small>
                    Limit {maxDebtBurdenPct.toFixed(1)}%
                  </small>
                </article>
              </div>
            )}
          </section>

          <section className="panel audit-footer">
            <h2>Run audit</h2>
            <div className="audit-grid">
              <span>
                Run ID
                <strong>
                  {analysis.audit_manifest?.run_id || "Unavailable"}
                </strong>
              </span>
              <span>
                Engine
                <strong>
                  {analysis.audit_manifest?.engine_version || "Unavailable"}
                </strong>
              </span>
              <span>
                Classifier
                <strong>
                  {analysis.audit_manifest?.classifier_model || "Unavailable"}
                </strong>
              </span>
              <span>
                Vision
                <strong>
                  {analysis.audit_manifest?.vision_model || "Unavailable"}
                </strong>
              </span>
            </div>
          </section>
        </>
      )}
    </main>
  );
}
