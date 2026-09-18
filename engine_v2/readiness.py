from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Protocol


class ReadinessStatus(str, Enum):
    READY = "READY"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    BLOCKED = "BLOCKED"


class _StatementLike(Protocol):
    source_file: str
    coverage: object | None
    extraction_quality: object | None
    composite_integrity: object | None
    integrity: object | None
    reconciliation_status: str | None


class _TransactionLike(Protocol):
    direction: str
    needs_review: bool


class _RevenueBaselineLike(Protocol):
    average_monthly_true_revenue: float
    basis: str


@dataclass(frozen=True)
class DecisionReadiness:
    status: ReadinessStatus
    automated_offer_allowed: bool
    blocking_reasons: tuple[str, ...] = ()
    review_reasons: tuple[str, ...] = ()
    checks: dict[str, str] = field(default_factory=dict)


def assess_decision_readiness(
    *,
    statements: Iterable[_StatementLike],
    transactions: Iterable[_TransactionLike],
    revenue_baseline: _RevenueBaselineLike | None,
) -> DecisionReadiness:
    statements = list(statements)
    transactions = list(transactions)

    blocking: list[str] = []
    review: list[str] = []
    checks: dict[str, str] = {}

    if not statements:
        blocking.append("No bank statements were processed.")
        checks["documents"] = "FAIL"
    else:
        checks["documents"] = "PASS"

    if not transactions:
        blocking.append("No ledger transactions were extracted.")
        checks["ledger"] = "FAIL"
    else:
        checks["ledger"] = "PASS"

    low_quality_files: list[str] = []
    moderate_quality_files: list[str] = []
    recon_fail_files: list[str] = []
    recon_warning_files: list[str] = []
    high_integrity_files: list[str] = []
    review_integrity_files: list[str] = []
    partial_files: list[str] = []
    unknown_coverage_files: list[str] = []

    for statement in statements:
        quality = getattr(statement, "extraction_quality", None)
        if quality is None:
            moderate_quality_files.append(statement.source_file)
        elif getattr(quality, "status", None) == "LOW":
            low_quality_files.append(statement.source_file)
        elif getattr(quality, "status", None) == "MODERATE":
            moderate_quality_files.append(statement.source_file)

        reconciliation = getattr(statement, "reconciliation_status", None)
        if reconciliation == "FAIL":
            recon_fail_files.append(statement.source_file)
        elif reconciliation == "WARNING":
            recon_warning_files.append(statement.source_file)

        integrity = (
            getattr(statement, "composite_integrity", None)
            or getattr(statement, "integrity", None)
        )
        integrity_status = getattr(integrity, "status", None)
        if integrity_status == "HIGH_REVIEW":
            high_integrity_files.append(statement.source_file)
        elif integrity_status == "REVIEW":
            review_integrity_files.append(statement.source_file)

        coverage = getattr(statement, "coverage", None)
        coverage_status = getattr(getattr(coverage, "status", None), "value", None)
        if coverage_status == "PARTIAL":
            partial_files.append(statement.source_file)
        elif coverage is None or coverage_status == "UNKNOWN":
            unknown_coverage_files.append(statement.source_file)

    if low_quality_files:
        blocking.append(
            "Low extraction quality: " + ", ".join(sorted(low_quality_files))
        )
        checks["extraction_quality"] = "FAIL"
    elif moderate_quality_files:
        review.append(
            "Moderate or unverified extraction quality: "
            + ", ".join(sorted(moderate_quality_files))
        )
        checks["extraction_quality"] = "REVIEW"
    else:
        checks["extraction_quality"] = "PASS"

    if recon_fail_files:
        blocking.append(
            "Ledger reconciliation failed: "
            + ", ".join(sorted(recon_fail_files))
        )
        checks["reconciliation"] = "FAIL"
    elif recon_warning_files:
        review.append(
            "Ledger reconciliation requires review: "
            + ", ".join(sorted(recon_warning_files))
        )
        checks["reconciliation"] = "REVIEW"
    else:
        checks["reconciliation"] = "PASS"

    if high_integrity_files:
        blocking.append(
            "High document-integrity concern: "
            + ", ".join(sorted(high_integrity_files))
        )
        checks["integrity"] = "FAIL"
    elif review_integrity_files:
        review.append(
            "Document-integrity review required: "
            + ", ".join(sorted(review_integrity_files))
        )
        checks["integrity"] = "REVIEW"
    else:
        checks["integrity"] = "PASS"

    if partial_files:
        review.append(
            "Partial statement period: " + ", ".join(sorted(partial_files))
        )
    if unknown_coverage_files:
        review.append(
            "Statement coverage could not be verified: "
            + ", ".join(sorted(unknown_coverage_files))
        )
    checks["coverage"] = (
        "REVIEW"
        if partial_files or unknown_coverage_files
        else "PASS"
    )

    unresolved_credits = sum(
        1
        for transaction in transactions
        if transaction.direction == "credit" and transaction.needs_review
    )
    if unresolved_credits:
        review.append(
            f"{unresolved_credits} credit transaction(s) still require "
            "classification review."
        )
        checks["classification"] = "REVIEW"
    else:
        checks["classification"] = "PASS"

    if (
        revenue_baseline is None
        or revenue_baseline.average_monthly_true_revenue <= 0
    ):
        blocking.append("No positive true-revenue baseline is available.")
        checks["revenue_baseline"] = "FAIL"
    elif revenue_baseline.basis == "OBSERVED_COVERAGE_UNVERIFIED":
        review.append(
            "Revenue baseline is based on observed but unverified coverage."
        )
        checks["revenue_baseline"] = "REVIEW"
    else:
        checks["revenue_baseline"] = "PASS"

    if blocking:
        return DecisionReadiness(
            status=ReadinessStatus.BLOCKED,
            automated_offer_allowed=False,
            blocking_reasons=tuple(blocking),
            review_reasons=tuple(review),
            checks=checks,
        )

    if review:
        return DecisionReadiness(
            status=ReadinessStatus.REVIEW_REQUIRED,
            automated_offer_allowed=False,
            blocking_reasons=(),
            review_reasons=tuple(review),
            checks=checks,
        )

    return DecisionReadiness(
        status=ReadinessStatus.READY,
        automated_offer_allowed=True,
        checks=checks,
    )
