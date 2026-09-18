from datetime import date
from decimal import Decimal

from engine_v2.models import TransactionDirection, TransactionRecord
from engine_v2.regression import compare_statement_to_manifest
from engine_v2.statement_parser import ParsedStatement


def _transaction(
    transaction_id: str,
    *,
    day: int,
    amount: str,
    direction: TransactionDirection,
    description: str,
):
    return TransactionRecord(
        transaction_id=transaction_id,
        statement_id="stmt_1",
        source_file="sample.pdf",
        page=1,
        transaction_date=date(2026, 8, day),
        description=description,
        amount=Decimal(amount),
        direction=direction,
    )


def test_golden_comparator_matches_expected_ledger():
    statement = ParsedStatement(
        statement_id="stmt_1",
        source_file="sample.pdf",
        file_sha256="abc",
        bank_id="RBC",
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 31),
        transactions=[
            _transaction(
                "t1",
                day=5,
                amount="8421.32",
                direction=TransactionDirection.CREDIT,
                description="ACH CREDIT STRIPE PAYOUT",
            ),
            _transaction(
                "t2",
                day=6,
                amount="1200.00",
                direction=TransactionDirection.DEBIT,
                description="RENT",
            ),
        ],
        reconciliation_status="PASS",
    )

    result = compare_statement_to_manifest(
        case_name="sample",
        statement=statement,
        manifest={
            "bank_id": "RBC",
            "period_start": "2026-08-01",
            "period_end": "2026-08-31",
            "transaction_count": 2,
            "credit_total": 8421.32,
            "debit_total": 1200,
            "reconciliation_status": "PASS",
            "transactions": [
                {
                    "date": "2026-08-05",
                    "direction": "credit",
                    "amount": 8421.32,
                    "description_contains": "STRIPE",
                }
            ],
        },
    )

    assert result.passed
    assert result.transaction_recall == 1.0
