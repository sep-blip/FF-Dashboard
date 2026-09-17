from datetime import date
from decimal import Decimal

from engine_v2.integrity import evaluate_statement_integrity
from engine_v2.models import (
    CoverageStatus,
    ReconciliationResult,
    ReconciliationStatus,
    StatementCoverage,
)


def test_failed_reconciliation_drives_high_review():
    coverage = StatementCoverage(
        statement_id="s1",
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 31),
        expected_days=31,
        observed_days=31,
        coverage_pct=100,
        status=CoverageStatus.COMPLETE,
    )
    recon = ReconciliationResult(
        statement_id="s1",
        total_credits=Decimal("1000"),
        total_debits=Decimal("500"),
        status=ReconciliationStatus.FAIL,
        variance=Decimal("500"),
        warning="failed",
    )
    report = evaluate_statement_integrity(
        coverage=coverage,
        reconciliation=recon,
        duplicate_transaction_count=10,
    )
    assert report.score <= 40
    assert report.status == "HIGH_REVIEW"
