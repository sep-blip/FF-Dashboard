from datetime import date
from decimal import Decimal

from engine_v2.models import TransactionDirection, TransactionRecord
from engine_v2.wash import detect_explicit_round_trips


def _txn(txn_id, day, amount, direction, description):
    return TransactionRecord(
        transaction_id=txn_id,
        statement_id="s1",
        source_file="statement.pdf",
        page=1,
        transaction_date=date(2026, 8, day),
        description=description,
        amount=Decimal(amount),
        direction=direction,
    )


def test_explicit_matching_transfer_reference_is_round_trip():
    rows = [
        _txn(
            "c1",
            2,
            "5000.00",
            TransactionDirection.CREDIT,
            "ONLINE TRANSFER TF 3978#1967-174",
        ),
        _txn(
            "d1",
            3,
            "5000.00",
            TransactionDirection.DEBIT,
            "TRANSFER TF 3978#1967-174",
        ),
    ]

    matches = detect_explicit_round_trips(rows)
    assert len(matches) == 1
    assert matches[0].credit_transaction_id == "c1"


def test_same_reference_different_amount_is_not_forced_to_match():
    rows = [
        _txn(
            "c1",
            2,
            "5000.00",
            TransactionDirection.CREDIT,
            "TRANSFER TF 3978#1967-174",
        ),
        _txn(
            "d1",
            3,
            "9000.00",
            TransactionDirection.DEBIT,
            "TRANSFER TF 3978#1967-174",
        ),
    ]

    assert detect_explicit_round_trips(rows) == []
