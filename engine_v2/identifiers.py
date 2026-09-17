from __future__ import annotations

import hashlib
import re
from datetime import date
from decimal import Decimal


def normalize_description(value: str) -> str:
    value = re.sub(r"\s+", " ", str(value or "").strip().upper())
    return value


def stable_statement_id(*, file_sha256: str, account_hint: str = "") -> str:
    payload = f"{file_sha256}|{normalize_description(account_hint)}"
    return "stmt_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def stable_transaction_id(
    *,
    statement_id: str,
    transaction_date: date | str,
    description: str,
    amount: Decimal | float | str,
    direction: str,
    page: int | None = None,
    occurrence: int = 0,
) -> str:
    """Create a repeatable lineage ID for an extracted transaction.

    occurrence disambiguates legitimate identical transactions on the same
    statement while keeping the ID stable across re-processing.
    """
    amount_decimal = Decimal(str(amount)).quantize(Decimal("0.01"))
    payload = "|".join(
        [
            statement_id,
            str(transaction_date),
            normalize_description(description),
            f"{amount_decimal:.2f}",
            str(direction).lower(),
            str(page or 0),
            str(occurrence),
        ]
    )
    return "txn_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
