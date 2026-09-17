from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable

from .constants import ALLOWED_CATEGORIES, REVIEW_REQUIRED


@dataclass(frozen=True)
class AiClassificationDecision:
    transaction_id: str
    category: str
    requires_review: bool
    reason: str
    evidence_terms: tuple[str, ...]
    model_name: str


def categorization_schema() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "transaction_categorization_v2",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "decisions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "transaction_id": {"type": "string"},
                                "category": {
                                    "type": "string",
                                    "enum": list(ALLOWED_CATEGORIES),
                                },
                                "requires_review": {"type": "boolean"},
                                "reason": {"type": "string"},
                                "evidence_terms": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                            },
                            "required": [
                                "transaction_id",
                                "category",
                                "requires_review",
                                "reason",
                                "evidence_terms",
                            ],
                            "additionalProperties": False,
                        },
                    }
                },
                "required": ["decisions"],
                "additionalProperties": False,
            },
        },
    }


def build_payload(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    payload = []
    for row in rows:
        payload.append(
            {
                "transaction_id": str(row["transaction_id"]),
                "date": str(row.get("date") or ""),
                "description": str(row.get("description") or ""),
                "amount": round(float(row.get("amount") or 0.0), 2),
                "direction": str(row.get("tx_type") or row.get("direction") or "credit"),
            }
        )
    return payload


SYSTEM_INSTRUCTIONS = """You classify unresolved bank-statement transactions for an MCA underwriting system.

You are NOT the accounting engine and must not calculate revenue totals, debt ratios, balances, or funding amounts.

Use only the supplied transaction fields. Follow these conservative rules:
- Generic ACH, EFT, wire, transfer, e-transfer, deposit, or payment wording is NOT enough to prove business revenue.
- Known or likely loan/MCA funding proceeds are non-revenue.
- Own-account transfers, shareholder contributions, refunds, reversals, government/tax/insurance proceeds, and wash/round-trip transfers are non-revenue.
- Classify as true revenue only when the description contains affirmative evidence of ordinary customer/business receipts, a payment processor settlement, verified cash sales, or a clearly identifiable B2B customer payment.
- If the evidence is insufficient, unusual, contradictory, or could reasonably be financing/transfer activity, use Review Required.
- requires_review must be true whenever an underwriter should verify the classification.
- evidence_terms should contain only short terms actually present in the transaction description. Do not invent counterparties.
- Keep the reason concise and transaction-specific.
"""


def classify_unresolved_transactions(
    *,
    client: Any,
    rows: Iterable[dict[str, Any]],
    model: str = "gpt-5.6-terra",
    timeout: float = 45.0,
) -> dict[str, AiClassificationDecision]:
    payload = build_payload(rows)
    if not payload:
        return {}

    expected_ids = {row["transaction_id"] for row in payload}

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_INSTRUCTIONS},
            {"role": "user", "content": json.dumps(payload)},
        ],
        response_format=categorization_schema(),
        timeout=timeout,
    )

    raw = json.loads(response.choices[0].message.content)
    decisions: dict[str, AiClassificationDecision] = {}

    for item in raw.get("decisions", []):
        transaction_id = str(item.get("transaction_id", ""))
        if transaction_id not in expected_ids or transaction_id in decisions:
            continue

        requires_review = bool(item["requires_review"])
        category = str(item["category"])
        # A model cannot auto-approve a row that it also says needs review.
        if requires_review:
            category = REVIEW_REQUIRED

        decisions[transaction_id] = AiClassificationDecision(
            transaction_id=transaction_id,
            category=category,
            requires_review=requires_review,
            reason=str(item["reason"]),
            evidence_terms=tuple(str(v) for v in item.get("evidence_terms", [])),
            model_name=model,
        )

    # Missing model outputs fail closed to manual review.
    for transaction_id in expected_ids - decisions.keys():
        decisions[transaction_id] = AiClassificationDecision(
            transaction_id=transaction_id,
            category=REVIEW_REQUIRED,
            requires_review=True,
            reason="Model returned no valid decision for this transaction.",
            evidence_terms=(),
            model_name=model,
        )

    return decisions
