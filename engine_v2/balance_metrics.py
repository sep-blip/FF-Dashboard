from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Iterable

from .models import TransactionDirection
from .statement_parser import ParsedStatement


@dataclass(frozen=True)
class BalanceMetrics:
    average_daily_balance: float
    negative_days: int
    observed_days: int
    statements_used: int
    excluded_statements: tuple[str, ...]


def calculate_balance_metrics(
    statements: Iterable[ParsedStatement],
    *,
    require_reconciliation_pass: bool = True,
) -> BalanceMetrics:
    """Reconstruct daily ending balances from the extracted ledger.

    For a reconciled statement, opening balance + all extracted daily activity
    gives a deterministic daily-ending balance series, including no-activity
    days via carry-forward. Statements missing dates/opening balance, or failing
    reconciliation when require_reconciliation_pass=True, are excluded.
    """
    daily_balances: list[Decimal] = []
    statements_used = 0
    excluded: list[str] = []

    for statement in statements:
        if (
            statement.period_start is None
            or statement.period_end is None
            or statement.opening_balance is None
        ):
            excluded.append(statement.source_file)
            continue

        if (
            require_reconciliation_pass
            and statement.reconciliation_status != "PASS"
        ):
            excluded.append(statement.source_file)
            continue

        if statement.period_end < statement.period_start:
            excluded.append(statement.source_file)
            continue

        activity: dict = {}
        for transaction in statement.transactions:
            if not (
                statement.period_start
                <= transaction.transaction_date
                <= statement.period_end
            ):
                continue

            signed_amount = (
                transaction.amount
                if transaction.direction == TransactionDirection.CREDIT
                else -transaction.amount
            )
            activity[transaction.transaction_date] = (
                activity.get(transaction.transaction_date, Decimal("0"))
                + signed_amount
            )

        balance = statement.opening_balance
        current = statement.period_start
        statement_daily: list[Decimal] = []

        while current <= statement.period_end:
            balance += activity.get(current, Decimal("0"))
            statement_daily.append(balance)
            current += timedelta(days=1)

        if not statement_daily:
            excluded.append(statement.source_file)
            continue

        daily_balances.extend(statement_daily)
        statements_used += 1

    if not daily_balances:
        return BalanceMetrics(
            average_daily_balance=0.0,
            negative_days=0,
            observed_days=0,
            statements_used=0,
            excluded_statements=tuple(excluded),
        )

    average = sum(daily_balances, Decimal("0")) / len(daily_balances)
    negative_days = sum(1 for balance in daily_balances if balance < 0)

    return BalanceMetrics(
        average_daily_balance=round(float(average), 2),
        negative_days=negative_days,
        observed_days=len(daily_balances),
        statements_used=statements_used,
        excluded_statements=tuple(excluded),
    )
