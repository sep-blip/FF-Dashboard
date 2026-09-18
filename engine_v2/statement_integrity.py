from __future__ import annotations

from collections import Counter

from pydantic import BaseModel, Field

from .integrity import IntegrityFinding, evaluate_statement_integrity
from .models import ReconciliationResult, StatementCoverage, TransactionRecord
from .pdf_integrity import PdfIntegrityReport


class StatementIntegrityAssessment(BaseModel):
    score: int = Field(ge=0, le=100)
    status: str
    structural_score: int = Field(ge=0, le=100)
    ledger_score: int = Field(ge=0, le=100)
    duplicate_extraction_count: int = Field(ge=0)
    findings: list[IntegrityFinding] = Field(default_factory=list)


def count_probable_duplicate_extractions(
    transactions: list[TransactionRecord],
) -> int:
    """Count repeated extracted rows using source-page and raw-line evidence.

    This deliberately uses source page + raw text, not merely equal amounts and
    descriptions, because merchants can legitimately have repeated identical
    payments. The signal is aimed at duplicate extraction artifacts.
    """
    signatures = [
        (
            transaction.page,
            transaction.transaction_date,
            transaction.direction.value,
            transaction.amount,
            transaction.raw_text,
        )
        for transaction in transactions
    ]
    counts = Counter(signatures)
    return sum(max(0, count - 1) for count in counts.values())


def assess_statement_integrity(
    *,
    structural: PdfIntegrityReport,
    coverage: StatementCoverage | None,
    reconciliation: ReconciliationResult,
    transactions: list[TransactionRecord],
) -> StatementIntegrityAssessment:
    duplicate_count = count_probable_duplicate_extractions(transactions)
    ledger = evaluate_statement_integrity(
        coverage=coverage,
        reconciliation=reconciliation,
        duplicate_transaction_count=duplicate_count,
    )

    # Ledger math receives slightly more weight because it directly tests
    # whether extracted activity reproduces the statement balances.
    composite = round(
        (structural.score * 0.45)
        + (ledger.score * 0.55)
    )

    if reconciliation.status.value == "FAIL":
        composite = min(composite, 55)

    composite = max(0, min(100, composite))
    status = (
        "LOW_CONCERN"
        if composite >= 85
        else "REVIEW"
        if composite >= 65
        else "HIGH_REVIEW"
    )

    findings = list(structural.findings) + list(ledger.findings)

    return StatementIntegrityAssessment(
        score=composite,
        status=status,
        structural_score=structural.score,
        ledger_score=ledger.score,
        duplicate_extraction_count=duplicate_count,
        findings=findings,
    )
