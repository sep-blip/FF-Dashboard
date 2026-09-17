from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from .models import CoverageStatus, ReconciliationResult, ReconciliationStatus, StatementCoverage


class FindingSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    HIGH = "HIGH"


class IntegrityFinding(BaseModel):
    code: str
    severity: FindingSeverity
    message: str
    evidence: dict = Field(default_factory=dict)


class IntegrityReport(BaseModel):
    score: int = Field(ge=0, le=100)
    status: str
    findings: list[IntegrityFinding] = Field(default_factory=list)


def evaluate_statement_integrity(
    *,
    coverage: StatementCoverage | None,
    reconciliation: ReconciliationResult | None,
    duplicate_transaction_count: int = 0,
) -> IntegrityReport:
    """Build an evidence-based integrity score without declaring fraud.

    This is deliberately a triage signal. A low score means manual review is
    warranted; it is not proof that a document was altered.
    """
    score = 100
    findings: list[IntegrityFinding] = []

    if coverage is None or coverage.status == CoverageStatus.UNKNOWN:
        score -= 8
        findings.append(
            IntegrityFinding(
                code="COVERAGE_UNKNOWN",
                severity=FindingSeverity.WARNING,
                message="Statement period could not be verified.",
            )
        )
    elif coverage.status == CoverageStatus.PARTIAL:
        score -= 5
        findings.append(
            IntegrityFinding(
                code="PARTIAL_PERIOD",
                severity=FindingSeverity.INFO,
                message=coverage.warning or "Statement covers a partial period.",
                evidence={"coverage_pct": coverage.coverage_pct},
            )
        )

    if reconciliation is None:
        score -= 15
        findings.append(
            IntegrityFinding(
                code="RECON_NOT_AVAILABLE",
                severity=FindingSeverity.WARNING,
                message="Full ledger reconciliation was not available.",
            )
        )
    elif reconciliation.status == ReconciliationStatus.WARNING:
        score -= 15
        findings.append(
            IntegrityFinding(
                code="RECON_WARNING",
                severity=FindingSeverity.WARNING,
                message=reconciliation.warning or "Ledger reconciliation warning.",
                evidence={"variance": str(reconciliation.variance)},
            )
        )
    elif reconciliation.status == ReconciliationStatus.FAIL:
        score -= 40
        findings.append(
            IntegrityFinding(
                code="RECON_FAIL",
                severity=FindingSeverity.HIGH,
                message=reconciliation.warning or "Ledger reconciliation failed.",
                evidence={"variance": str(reconciliation.variance)},
            )
        )

    if duplicate_transaction_count:
        penalty = min(20, 2 * duplicate_transaction_count)
        score -= penalty
        findings.append(
            IntegrityFinding(
                code="DUPLICATE_TRANSACTIONS",
                severity=FindingSeverity.WARNING,
                message=f"Detected {duplicate_transaction_count} duplicate transaction rows.",
                evidence={"count": duplicate_transaction_count},
            )
        )

    score = max(0, min(100, score))
    status = "LOW_CONCERN" if score >= 85 else "REVIEW" if score >= 65 else "HIGH_REVIEW"
    return IntegrityReport(score=score, status=status, findings=findings)
