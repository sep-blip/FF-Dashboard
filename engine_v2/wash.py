from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Iterable

from .classification import extract_transfer_reference
from .models import TransactionDirection, TransactionRecord


@dataclass(frozen=True)
class WashMatch:
    reference: str
    credit_transaction_id: str
    debit_transaction_id: str
    credit_amount: Decimal
    debit_amount: Decimal
    credit_date: str
    debit_date: str
    amount_variance: Decimal


def detect_explicit_round_trips(
    transactions: Iterable[TransactionRecord],
    *,
    amount_tolerance: Decimal = Decimal("1.00"),
    max_days_apart: int = 7,
) -> list[WashMatch]:
    """Find explicit debit/credit round trips sharing an account-transfer ref.

    The detector is intentionally conservative: a credit is flagged only when
    the same normalized transfer reference appears on a debit and the amounts
    agree within tolerance inside a short date window. This is a revenue-quality
    signal, not a declaration of fraud.
    """
    credits: dict[str, list[TransactionRecord]] = {}
    debits: dict[str, list[TransactionRecord]] = {}

    for transaction in transactions:
        reference = extract_transfer_reference(transaction.description)
        if not reference:
            continue
        target = (
            credits
            if transaction.direction == TransactionDirection.CREDIT
            else debits
        )
        target.setdefault(reference, []).append(transaction)

    matches: list[WashMatch] = []
    used_debits: set[str] = set()

    for reference, credit_rows in credits.items():
        debit_rows = debits.get(reference, [])
        if not debit_rows:
            continue

        for credit in sorted(
            credit_rows,
            key=lambda row: (row.transaction_date, row.amount),
        ):
            candidates = []
            for debit in debit_rows:
                if debit.transaction_id in used_debits:
                    continue

                day_gap = abs(
                    (credit.transaction_date - debit.transaction_date).days
                )
                if day_gap > max_days_apart:
                    continue

                variance = abs(credit.amount - debit.amount)
                if variance > amount_tolerance:
                    continue

                candidates.append((variance, day_gap, debit))

            if not candidates:
                continue

            variance, _, debit = min(
                candidates,
                key=lambda item: (item[0], item[1]),
            )
            used_debits.add(debit.transaction_id)
            matches.append(
                WashMatch(
                    reference=reference,
                    credit_transaction_id=credit.transaction_id,
                    debit_transaction_id=debit.transaction_id,
                    credit_amount=credit.amount,
                    debit_amount=debit.amount,
                    credit_date=credit.transaction_date.isoformat(),
                    debit_date=debit.transaction_date.isoformat(),
                    amount_variance=variance,
                )
            )

    return matches
