from datetime import date
from decimal import Decimal

from engine_v2.models import (
    ReconciliationResult,
    ReconciliationStatus,
    TransactionDirection,
    TransactionRecord,
)
from engine_v2.pdf_integrity import PdfIntegrityReport
from engine_v2.statement_integrity import assess_statement_integrity


def test_reconciliation_failure_caps_composite_score():
    structural = PdfIntegrityReport(
        score=100,
        status="LOW_CONCERN",
        page_count=1,
    )
    recon = ReconciliationResult(
        statement_id="s1",
        total_credits=Decimal("100"),
        total_debits=Decimal("0"),
        variance=Decimal("500"),
        status=ReconciliationStatus.FAIL,
        warning="mismatch",
    )
    transaction = TransactionRecord(
        transaction_id="t1",
        statement_id="s1",
        source_file="a.pdf",
        page=1,
        transaction_date=date(2026, 1, 1),
        description="Deposit",
        amount=Decimal("100"),
        direction=TransactionDirection.CREDIT,
        raw_text="01 Jan Deposit 100.00",
    )

    result = assess_statement_integrity(
        structural=structural,
        coverage=None,
        reconciliation=recon,
        transactions=[transaction],
    )
    assert result.score <= 55
    assert result.status == "HIGH_REVIEW"
