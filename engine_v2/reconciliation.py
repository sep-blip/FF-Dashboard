from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Optional

from .models import ReconciliationResult, ReconciliationStatus, TransactionDirection, TransactionRecord


def reconcile_statement(
    *,
    statement_id: str,
    transactions: Iterable[TransactionRecord],
    opening_balance: Optional[Decimal],
    closing_balance: Optional[Decimal],
    tolerance: Decimal = Decimal("2.00"),
) -> ReconciliationResult:
    """Reconcile extracted ledger math deterministically.

    This function performs no LLM work. It is intended to be the accounting
    control that catches extraction errors before underwriting calculations run.
    """

    txns = list(transactions)
    credits = sum(
        (t.amount for t in txns if t.direction == TransactionDirection.CREDIT),
        Decimal("0"),
    )
    debits = sum(
        (t.amount for t in txns if t.direction == TransactionDirection.DEBIT),
        Decimal("0"),
    )

    if opening_balance is None or closing_balance is None:
        return ReconciliationResult(
            statement_id=statement_id,
            opening_balance=opening_balance,
            closing_balance=closing_balance,
            total_credits=credits,
            total_debits=debits,
            status=ReconciliationStatus.WARNING,
            tolerance=tolerance,
            warning=(
                "Opening or closing balance is unavailable. Ledger totals were "
                "computed, but full balance reconciliation could not be performed."
            ),
        )

    calculated = opening_balance + credits - debits
    variance = abs(calculated - closing_balance)

    if variance <= tolerance:
        status = ReconciliationStatus.PASS
        warning = None
    elif variance <= tolerance * Decimal("5"):
        status = ReconciliationStatus.WARNING
        warning = (
            f"Reconciliation variance is {variance}. Review extraction before "
            "using the statement for a final offer."
        )
    else:
        status = ReconciliationStatus.FAIL
        warning = (
            f"Reconciliation variance is {variance}. Underwriting calculations "
            "should not be finalized until the extraction is corrected or reviewed."
        )

    return ReconciliationResult(
        statement_id=statement_id,
        opening_balance=opening_balance,
        closing_balance=closing_balance,
        total_credits=credits,
        total_debits=debits,
        calculated_closing_balance=calculated,
        variance=variance,
        tolerance=tolerance,
        status=status,
        warning=warning,
    )
