from datetime import date
from decimal import Decimal

from engine_v2.models import ReconciliationStatus, TransactionDirection, TransactionRecord
from engine_v2.reconciliation import reconcile_statement


def _txn(txn_id: str, amount: str, direction: TransactionDirection) -> TransactionRecord:
    return TransactionRecord(
        transaction_id=txn_id,
        statement_id="stmt-1",
        source_file="sample.pdf",
        transaction_date=date(2026, 9, 1),
        description="test",
        amount=Decimal(amount),
        direction=direction,
    )


def test_exact_reconciliation_passes():
    txns = [
        _txn("1", "500.00", TransactionDirection.CREDIT),
        _txn("2", "200.00", TransactionDirection.DEBIT),
    ]

    result = reconcile_statement(
        statement_id="stmt-1",
        transactions=txns,
        opening_balance=Decimal("1000.00"),
        closing_balance=Decimal("1300.00"),
    )

    assert result.status == ReconciliationStatus.PASS
    assert result.variance == Decimal("0.00")


def test_missing_balance_returns_warning_not_failure():
    result = reconcile_statement(
        statement_id="stmt-1",
        transactions=[],
        opening_balance=None,
        closing_balance=None,
    )

    assert result.status == ReconciliationStatus.WARNING
