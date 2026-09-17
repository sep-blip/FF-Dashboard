from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from statistics import median
from typing import Iterable

from pydantic import BaseModel, Field

from .classification import detect_lender


class McaDebit(BaseModel):
    transaction_id: str | None = None
    transaction_date: date
    description: str
    lender: str
    tier: str
    payment_amount: float = Field(gt=0)


class McaPosition(BaseModel):
    lender: str
    tier: str
    payment_amount: float = Field(ge=0)
    frequency: str
    monthly_payment: float = Field(ge=0)
    observed_payments: int = Field(ge=1)
    first_observed_date: date
    last_observed_date: date


def monthly_equivalent(payment_amount: float, frequency: str) -> float:
    multipliers = {
        "Daily": 21.0,
        "2-3x Weekly": 9.0,
        "Weekly": 4.33,
        "Bi-Weekly": 2.16,
        "Monthly": 1.0,
    }
    return round(float(payment_amount) * multipliers.get(frequency, 1.0), 2)


def infer_frequency(dates: Iterable[date]) -> str:
    ordered = sorted(set(dates))
    if len(ordered) < 2:
        return "Monthly"

    intervals = [(b - a).days for a, b in zip(ordered, ordered[1:]) if (b - a).days > 0]
    if not intervals:
        return "Monthly"

    med = median(intervals)
    if med <= 2:
        return "Daily"
    if med <= 5:
        return "2-3x Weekly"
    if med <= 8:
        return "Weekly"
    if med <= 15:
        return "Bi-Weekly"
    return "Monthly"


def build_mca_debit(
    *,
    transaction_date: date,
    description: str,
    amount: float,
    transaction_id: str | None = None,
) -> McaDebit | None:
    lender = detect_lender(description)
    if not lender:
        return None
    tier, canonical = lender
    return McaDebit(
        transaction_id=transaction_id,
        transaction_date=transaction_date,
        description=description,
        lender=canonical,
        tier=tier,
        payment_amount=float(amount),
    )


def aggregate_positions(debits: Iterable[McaDebit]) -> list[McaPosition]:
    grouped: dict[str, list[McaDebit]] = {}
    for debit in debits:
        grouped.setdefault(debit.lender, []).append(debit)

    positions: list[McaPosition] = []
    for lender, rows in sorted(grouped.items()):
        rows = sorted(rows, key=lambda row: row.transaction_date)
        amounts = [round(row.payment_amount, 2) for row in rows]
        # Counter is deterministic on ties when amounts is date ordered.
        payment_amount = Counter(amounts).most_common(1)[0][0]
        frequency = infer_frequency(row.transaction_date for row in rows)
        positions.append(
            McaPosition(
                lender=lender,
                tier=rows[0].tier,
                payment_amount=payment_amount,
                frequency=frequency,
                monthly_payment=monthly_equivalent(payment_amount, frequency),
                observed_payments=len(rows),
                first_observed_date=rows[0].transaction_date,
                last_observed_date=rows[-1].transaction_date,
            )
        )
    return positions
