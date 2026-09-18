import { useMemo, useState } from "react";
import { analyzeStatements } from "./api";
import type { ClassifiedTransaction, StatementAnalysis } from "./types";

const money = new Intl.NumberFormat("en-CA", {
  style: "currency",
  currency: "CAD",
  maximumFractionDigits: 2,
});

function StatusPill({ value }: { value: string | null }) {
  const normalized = (value || "UNKNOWN").toUpperCase();
  const tone =
    normalized.includes("PASS") ||
    normalized.includes("COMPLETE") ||
    normalized.includes("LOW_CONCERN")
      ? "good"
      : normalized.includes("FAIL") ||
          normalized.includes("HIGH") ||
          normalized.includes("REVIEW")
        ? "risk"
        : "warn";

  return <span className={`pill ${tone}`}>{value || "Unknown"}</span>;
}

function TransactionTable({
  transactions,
}: {
  transactions: ClassifiedTransaction[];
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
            <th>Review</th>
          </tr>
        </thead>
        <tbody>
          {credits.map((txn) => (
            <tr key={txn.transaction_id}>
              <td>{txn.date}</td>
              <td>
                <strong>{txn.description}</strong>
                <small>{txn.classification_reason}</small>
              </td>
              <td>{money.format(txn.amount)}</td>
              <td>{txn.category}</td>
              <td>{txn.classification_source}</td>
              <td>
                {txn.needs_review ? (
                  <span className="pill risk">Required</span>
                ) : (
                  <span className="pill good">Clear</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function App() {
  const [files, setFiles] = useState<File[]>([]);
  const [enableOcr, setEnableOcr] = useState(false);
  const [useAi, setUseAi] = useState(true);
  const [analysis, setAnalysis] = useState<StatementAnalysis | null>(null);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reviewCount = useMemo(
    () =>
      analysis?.transactions.filter(
        (transaction) =>
          transaction.direction === "credit" && transaction.needs_review,
      ).length || 0,
    [analysis],
  );

  function downloadAnalysis() {
    if (!analysis) return;
    const blob = new Blob(
      [JSON.stringify(analysis, null, 2)],
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

  async function runAnalysis() {
    if (!files.length) return;
    setWorking(true);
    setError(null);
    try {
      setAnalysis(
        await analyzeStatements(files, {
          enableOcr,
          useAiClassifier: useAi,
        }),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed.");
    } finally {
      setWorking(false);
    }
  }

  return (
    <main className="page">
      <header className="topbar">
        <div>
          <p className="eyebrow">Forward Funding</p>
          <h1>Underwriting Workbench</h1>
          <p className="subtle">
            Statement extraction, true-revenue review, debt detection and
            integrity controls.
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
              "Native PDF extraction is used first."}
          </span>
        </label>

        <div className="controls">
          <label>
            <input
              type="checkbox"
              checked={useAi}
              onChange={(event) => setUseAi(event.target.checked)}
            />
            Use AI for unresolved credits
          </label>
          <label>
            <input
              type="checkbox"
              checked={enableOcr}
              onChange={(event) => setEnableOcr(event.target.checked)}
            />
            Enable OCR fallback
          </label>
          <button
            disabled={!files.length || working}
            onClick={runAnalysis}
          >
            {working ? "Analyzing…" : "Run underwriting analysis"}
          </button>
        </div>

        {error && <div className="alert risk-alert">{error}</div>}
      </section>

      {analysis && (
        <>
          {analysis.decision_readiness && (
            <section
              className={`panel readiness-card ${analysis.decision_readiness.status.toLowerCase()}`}
            >
              <div className="readiness-header">
                <div>
                  <p className="eyebrow">Decision readiness</p>
                  <h2>{analysis.decision_readiness.status.replaceAll("_", " ")}</h2>
                </div>
                <StatusPill value={analysis.decision_readiness.status} />
              </div>

              {analysis.decision_readiness.blocking_reasons.map((reason) => (
                <div className="alert risk-alert" key={reason}>
                  {reason}
                </div>
              ))}
              {analysis.decision_readiness.review_reasons.map((reason) => (
                <div className="alert warning-alert" key={reason}>
                  {reason}
                </div>
              ))}

              <div className="readiness-actions">
                <small>
                  Automated offer:{" "}
                  {analysis.decision_readiness.automated_offer_allowed
                    ? "allowed"
                    : "not allowed until controls are cleared"}
                </small>
                <button className="secondary-button" onClick={downloadAnalysis}>
                  Download analysis JSON
                </button>
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
                  analysis.revenue_baseline
                    ?.average_monthly_true_revenue || 0,
                )}
              </strong>
              <small>
                {analysis.revenue_baseline?.basis || "No baseline"}
              </small>
            </article>
            <article className="kpi">
              <span>Monthly debt service</span>
              <strong>
                {money.format(
                  analysis.debt_ratios?.total_monthly_debt_service || 0,
                )}
              </strong>
              <small>
                {analysis.mca_positions.length} detected position(s)
              </small>
            </article>
            <article className="kpi">
              <span>Total debt ratio</span>
              <strong>
                {(analysis.debt_ratios?.total_debt_ratio_pct || 0).toFixed(1)}%
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
            <h2>Statement controls</h2>
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
                        <small>{statement.bank_name || "Bank not identified"}</small>
                      </td>
                      <td>
                        <StatusPill value={statement.extraction_quality_status} />
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
            <h2>True-revenue reconciliation</h2>
            <TransactionTable transactions={analysis.transactions} />
          </section>
        </>
      )}
    </main>
  );
}
