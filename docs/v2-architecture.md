# Underwriting Engine V2

## Design goals

V2 separates document interpretation from financial arithmetic and policy
decisions. The system must continue processing imperfect documents where safe,
surface uncertainty explicitly, and preserve enough lineage to reproduce every
number shown to an underwriter.

## Processing flow

1. **Document ingestion**
   - hash every upload
   - reject byte-identical duplicates
   - assign a stable statement identifier
   - retain source-file and page lineage

2. **Extraction**
   - native positioned PDF extraction first
   - text fallback second
   - OCR/vision fallback only when required
   - never treat an LLM response as the canonical ledger

3. **Validation**
   - opening balance + credits - debits = closing balance
   - statement-period completeness
   - duplicate and chronology checks
   - extraction warnings remain attached to the statement

4. **Classification**
   - deterministic rules first
   - known processors -> true revenue
   - known lenders -> loan/MCA proceeds
   - internal transfers, reversals and government/tax items -> non-revenue
   - unresolved rows -> structured AI classification
   - low-confidence or unsupported rows -> human review

5. **Metrics**
   - all totals are calculated in Python
   - complete months drive the underwriting revenue baseline when available
   - partial months remain visible as observed values
   - projections are labeled estimates and do not silently drive a final offer

6. **Funding policy**
   - funding ceiling is deterministic
   - revenue multiple, debt burden, term, factor rate and absolute caps are
     explicit policy inputs
   - the recommended advance is the minimum of all applicable ceilings

7. **Auditability**
   - immutable transaction IDs
   - versioned classifications
   - metric snapshots
   - policy-versioned offers
   - human overrides and system actions written as audit events

## Current migration strategy

The existing Streamlit application remains functional while V2 components are
introduced behind it. The first migration integrates stable transaction IDs,
statement-coverage warnings, safer partial-month handling, and modular
classification. The REST API and PostgreSQL schema are introduced in parallel
so the UI can later become a React/Next.js client without rewriting the core
underwriting logic.
