from datetime import date
from decimal import Decimal

from engine_v2.balance_metrics import calculate_balance_metrics
from engine_v2.models import TransactionDirection, TransactionRecord
from engine_v2.statement_parser import ParsedStatement


def test_daily_balance_carries_forward_on_inactive_days():
    statement = ParsedStatement(
        statement_id="s1",
        source_file="aug.pdf",
        file_sha256="abc",
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 3),
        opening_balance=Decimal("1000"),
        reconciliation_status="PASS",
        transactions=[
            TransactionRecord(
                transaction_id="t1",
                statement_id="s1",
                source_file="aug.pdf",
                page=1,
                transaction_date=date(2026, 8, 1),
                description="DEPOSIT",
                amount=Decimal("500"),
                direction=TransactionDirection.CREDIT,
            ),
            TransactionRecord(
                transaction_id="t2",
                statement_id="s1",
                source_file="aug.pdf",
                page=1,
                transaction_date=date(2026, 8, 3),
                description="PAYMENT",
                amount=Decimal("1800"),
                direction=TransactionDirection.DEBIT,
            ),
        ],
    )

    result = calculate_balance_metrics([statement])
    # Daily endings: 1500, 1500, -300
    assert result.average_daily_balance == 900.0
    assert result.negative_days == 1
    assert result.observed_days == 3
    assert result.statements_used == 1


def test_unreconciled_statement_is_excluded():
    statement = ParsedStatement(
        statement_id="s1",
        source_file="bad.pdf",
        file_sha256="abc",
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 31),
        opening_balance=Decimal("1000"),
        reconciliation_status="FAIL",
    )
    result = calculate_balance_metrics([statement])
    assert result.statements_used == 0
    assert result.excluded_statements == ("bad.pdf",)
