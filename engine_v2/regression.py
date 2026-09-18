from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from .models import TransactionDirection
from .statement_parser import ParsedStatement


@dataclass(frozen=True)
class RegressionMismatch:
    code: str
    message: str


@dataclass
class RegressionResult:
    case_name: str
    passed: bool
    expected_transaction_count: int
    matched_transaction_count: int
    actual_transaction_count: int
    mismatches: list[RegressionMismatch] = field(default_factory=list)

    @property
    def transaction_recall(self) -> float:
        if self.expected_transaction_count == 0:
            return 1.0
        return self.matched_transaction_count / self.expected_transaction_count


def _total_by_direction(
    statement: ParsedStatement,
    direction: TransactionDirection,
) -> Decimal:
    return sum(
        (
            transaction.amount
            for transaction in statement.transactions
            if transaction.direction == direction
        ),
        Decimal("0"),
    )


def _matches_expected_transaction(
    actual,
    expected: dict[str, Any],
    *,
    amount_tolerance: Decimal,
) -> bool:
    if expected.get("date") and actual.transaction_date.isoformat() != expected["date"]:
        return False
    if expected.get("direction") and actual.direction.value != expected["direction"]:
        return False

    if "amount" in expected:
        expected_amount = Decimal(str(expected["amount"]))
        if abs(actual.amount - expected_amount) > amount_tolerance:
            return False

    description_contains = expected.get("description_contains")
    if description_contains:
        if str(description_contains).upper() not in actual.description.upper():
            return False

    return True


def compare_statement_to_manifest(
    *,
    case_name: str,
    statement: ParsedStatement,
    manifest: dict[str, Any],
    amount_tolerance: Decimal = Decimal("0.01"),
    total_tolerance: Decimal = Decimal("2.00"),
) -> RegressionResult:
    mismatches: list[RegressionMismatch] = []

    expected_bank = manifest.get("bank_id")
    if expected_bank and statement.bank_id != expected_bank:
        mismatches.append(
            RegressionMismatch(
                "BANK_ID",
                f"Expected bank {expected_bank}, got {statement.bank_id}.",
            )
        )

    expected_period_start = manifest.get("period_start")
    if expected_period_start:
        actual = (
            statement.period_start.isoformat()
            if statement.period_start else None
        )
        if actual != expected_period_start:
            mismatches.append(
                RegressionMismatch(
                    "PERIOD_START",
                    f"Expected period_start {expected_period_start}, got {actual}.",
                )
            )

    expected_period_end = manifest.get("period_end")
    if expected_period_end:
        actual = (
            statement.period_end.isoformat()
            if statement.period_end else None
        )
        if actual != expected_period_end:
            mismatches.append(
                RegressionMismatch(
                    "PERIOD_END",
                    f"Expected period_end {expected_period_end}, got {actual}.",
                )
            )

    expected_count = manifest.get("transaction_count")
    if expected_count is not None and len(statement.transactions) != int(expected_count):
        mismatches.append(
            RegressionMismatch(
                "TRANSACTION_COUNT",
                f"Expected {expected_count} transactions, got "
                f"{len(statement.transactions)}.",
            )
        )

    totals = {
        "credit_total": _total_by_direction(
            statement,
            TransactionDirection.CREDIT,
        ),
        "debit_total": _total_by_direction(
            statement,
            TransactionDirection.DEBIT,
        ),
    }
    for key, actual_total in totals.items():
        if key not in manifest:
            continue
        expected_total = Decimal(str(manifest[key]))
        if abs(actual_total - expected_total) > total_tolerance:
            mismatches.append(
                RegressionMismatch(
                    key.upper(),
                    f"Expected {key} {expected_total}, got {actual_total}.",
                )
            )

    expected_transactions = list(manifest.get("transactions") or [])
    unmatched_actual = list(statement.transactions)
    matched_count = 0

    for expected_transaction in expected_transactions:
        match_index = None
        for index, actual in enumerate(unmatched_actual):
            if _matches_expected_transaction(
                actual,
                expected_transaction,
                amount_tolerance=amount_tolerance,
            ):
                match_index = index
                break

        if match_index is None:
            mismatches.append(
                RegressionMismatch(
                    "MISSING_TRANSACTION",
                    f"Expected transaction not found: {expected_transaction}",
                )
            )
            continue

        matched_count += 1
        unmatched_actual.pop(match_index)

    minimum_recall = float(manifest.get("minimum_transaction_recall", 1.0))
    recall = (
        matched_count / len(expected_transactions)
        if expected_transactions else 1.0
    )
    if recall < minimum_recall:
        mismatches.append(
            RegressionMismatch(
                "TRANSACTION_RECALL",
                f"Transaction recall {recall:.3f} is below required "
                f"{minimum_recall:.3f}.",
            )
        )

    expected_reconciliation = manifest.get("reconciliation_status")
    if (
        expected_reconciliation
        and statement.reconciliation_status != expected_reconciliation
    ):
        mismatches.append(
            RegressionMismatch(
                "RECONCILIATION",
                f"Expected reconciliation {expected_reconciliation}, got "
                f"{statement.reconciliation_status}.",
            )
        )

    return RegressionResult(
        case_name=case_name,
        passed=not mismatches,
        expected_transaction_count=len(expected_transactions),
        matched_transaction_count=matched_count,
        actual_transaction_count=len(statement.transactions),
        mismatches=mismatches,
    )
