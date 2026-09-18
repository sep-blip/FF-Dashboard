# Underwriting Engine V2

## Design goals

V2 separates document interpretation from arithmetic and underwriting policy.
It continues processing imperfect statements where safe, surfaces uncertainty,
and preserves source lineage for every financial result.

V2 is stateless by design. No SQL database is required.

## Processing flow

1. **Document ingestion**
   - SHA-256 each upload
   - skip byte-identical duplicates
   - assign stable statement IDs
   - preserve source filename and page lineage

2. **Bank/template profiling**
   - identify supported Canadian bank signatures
   - record bank/template confidence separately from transaction extraction

3. **Extraction**
   - native positioned PDF text first
   - positioned English/French OCR second
   - guarded vision fallback only for pages that remain unreadable
   - vision/OCR rows are never trusted merely because a model produced them

4. **Validation**
   - opening balance + credits - debits = closing balance
   - independent deposit/credit anchors where available
   - statement-period completeness
   - duplicate-extraction checks
   - deterministic extraction-quality score
   - composite document-integrity score

5. **Classification**
   - deterministic rules first
   - known processors -> true revenue
   - known lenders -> MCA/loan proceeds
   - transfers, reversals and government/tax items -> non-revenue
   - unresolved credits -> structured AI classification
   - uncertain results fail closed to manual review

6. **Metrics**
   - totals calculated in Python
   - verified complete months drive the revenue baseline when available
   - partial months remain visible as observed values
   - debt service is normalized to a monthly basis

7. **Decision-readiness gate**
   - READY
   - REVIEW_REQUIRED
   - BLOCKED
   - low extraction quality, failed reconciliation or high integrity concern
     prevents an automated final offer

8. **Policy and funding**
   - deterministic scorecard
   - explicit revenue multiple
   - maximum total debt burden
   - factor rate
   - business-day term
   - optional absolute cap

9. **Auditability without a database**
   - stable transaction IDs
   - source filename/page lineage
   - classification source and model name
   - engine/model settings
   - source-document SHA-256 hashes
   - run ID and timestamp
   - downloadable JSON analysis artifact

10. **Regression testing**
    - private redacted golden-statement corpus
    - exact date/amount matching
    - transaction recall
    - credit/debit totals
    - statement-period detection
    - reconciliation expectations

## Interfaces

The core engine is UI-independent.

- FastAPI exposes the V2 services.
- React/Vite is the production-oriented dashboard.
- Streamlit remains as a migration/workbench interface.

## ML

The PD model framework is intentionally separated from the deterministic
funding-limit calculator. A PD model cannot be considered production-ready
until real historical outcome labels are available and the model passes
out-of-time validation, calibration, leakage, stability and governance review.
