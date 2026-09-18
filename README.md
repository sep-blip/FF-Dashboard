# Forward Funding Underwriting Engine

A bank-statement underwriting workbench for merchant cash advance / small
business funding. The V2 architecture is intentionally stateless: uploaded
documents are analyzed in memory and the finished analysis can be downloaded
as a self-contained JSON audit artifact.

## Core principle

The LLM does not calculate financial totals or funding amounts.

The system separates:

- document extraction;
- deterministic accounting controls;
- transaction classification;
- true-revenue calculations;
- MCA/debt detection;
- underwriting policy;
- document-integrity review;
- human review.

## Pipeline

```text
PDF statements
    |
    v
bank/template detection
    |
    v
native positioned extraction
    |
    +--> positioned OCR fallback (English + French)
    |
    +--> guarded vision fallback for unreadable pages
    |
    v
canonical transaction ledger
    |
    v
balance reconciliation + extraction quality + document integrity
    |
    v
rules-first classification
    |
    +--> structured AI classification for unresolved credits
    |
    v
true revenue + MCA positions + debt ratios
    |
    v
decision-readiness gate
    |
    v
deterministic scorecard / funding-capacity scenarios
```

## Reliability controls

- SHA-256 duplicate-file detection
- stable statement and transaction IDs
- page/source lineage for every extracted row
- opening + credits - debits = closing reconciliation
- partial-month detection without rejecting the statement
- complete months preferred for underwriting revenue baselines
- bank-template detection for major Canadian banks
- deterministic extraction-quality score
- composite statement-integrity review score
- fail-closed treatment of unresolved deposits
- vision/OCR-derived ledgers require additional review
- private golden-statement regression harness
- decision-readiness status: READY, REVIEW_REQUIRED, or BLOCKED

## Document extraction

V2 supports three extraction paths:

1. Native PDF positioned text
2. Tesseract positioned OCR for scanned pages
3. Vision-model fallback for pages native/OCR extraction cannot reliably read

Vision is a fallback, not a shortcut. Vision-derived transactions are still
subject to reconciliation and are capped at a review-required extraction
quality until validated.

## Revenue classification

Credits are categorized into classes including:

- True Revenue - POS / Processor
- True Revenue - Verified Cash
- True Revenue - Customer Payment / Cheque
- True Revenue - B2B E-Transfer
- Non-Revenue - Own-Account / Internal Transfer
- Non-Revenue - MCA / Loan Proceeds
- Non-Revenue - Refund / Reversal / NSF
- Non-Revenue - Gov / Tax / Insurance Proceeds
- Non-Revenue - Shareholder / Investment
- Non-Revenue - Wash / Round-Trip Transfer
- Review Required - Unidentified / Unusual Deposit

Known rules run before AI classification.

## Interfaces

### React dashboard

The V2 React/Vite dashboard provides:

- multi-statement upload
- OCR and vision fallback controls
- statement coverage
- extraction-quality score
- document-integrity status
- reconciliation status
- MCA position table
- true-revenue transaction review
- decision-readiness warnings
- deterministic funding-capacity scenarios
- JSON audit download

### FastAPI

Run:

```bash
uvicorn api.main:app --reload
```

Useful endpoints:

- `GET /health`
- `POST /v1/documents/bank-statements/analyze`
- `POST /v1/underwriting/revenue-baseline`
- `POST /v1/underwriting/funding-capacity`

### Streamlit

The original Streamlit workbench remains available while V2 is migrated:

```bash
streamlit run app.py
```

## Local Docker stack

Create `.env` from `.env.example`, then:

```bash
docker compose up --build
```

Open:

- React dashboard: http://localhost:8080
- API docs: http://localhost:8000/docs

No SQL database is required.

## OpenAI key

Set:

```text
OPENAI_API_KEY=...
```

Without an API key, native/OCR parsing and deterministic rules still work.
Unresolved credits remain in manual review and vision fallback is unavailable.

## Regression testing

Real merchant statements should never be committed to Git.

Maintain a private, redacted corpus under `regression_cases/` and run:

```bash
python tools/run_statement_regression.py regression_cases
```

See `docs/statement-regression.md`.

## PD model

The repository includes an XGBoost PD-model training/inference framework and
SHAP explanation support, but intentionally does not ship a fabricated trained
model. A credible PD model requires real historical performance labels and
out-of-time validation before it can influence underwriting decisions.

See `docs/pd-model.md`.
