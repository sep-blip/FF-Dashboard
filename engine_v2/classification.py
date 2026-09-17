from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from .constants import (
    GOV_TAX_INSURANCE_PATTERNS,
    INTERNAL_TRANSFER_PATTERNS,
    LENDER_ALIASES,
    NON_REVENUE_GOV,
    NON_REVENUE_INTERNAL,
    NON_REVENUE_MCA,
    NON_REVENUE_REVERSAL,
    NSF_REVERSAL_PATTERNS,
    POS_PROCESSOR_PATTERN,
    REVIEW_REQUIRED,
    TRUE_REVENUE_POS,
)


@dataclass(frozen=True)
class RuleClassification:
    category: str | None
    confidence: float
    reason: str
    lender_name: str | None = None
    lender_tier: str | None = None


def matches_any(patterns: Iterable[str], text: str) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def detect_lender(description: str) -> tuple[str, str] | None:
    text = str(description or "").upper()
    # Long aliases first so a short alias cannot shadow a more specific one.
    for alias in sorted(LENDER_ALIASES, key=len, reverse=True):
        if re.search(r"\b" + re.escape(alias) + r"\b", text):
            tier, canonical = LENDER_ALIASES[alias]
            return tier, canonical
    return None


def classify_by_rules(description: str, *, direction: str = "credit") -> RuleClassification:
    text = str(description or "").upper()

    if matches_any(INTERNAL_TRANSFER_PATTERNS, text):
        return RuleClassification(
            NON_REVENUE_INTERNAL,
            0.99,
            "Matched deterministic internal-transfer signature.",
        )

    if matches_any(NSF_REVERSAL_PATTERNS, text):
        return RuleClassification(
            NON_REVENUE_REVERSAL,
            0.98,
            "Matched deterministic refund/reversal/NSF signature.",
        )

    if matches_any(GOV_TAX_INSURANCE_PATTERNS, text):
        return RuleClassification(
            NON_REVENUE_GOV,
            0.97,
            "Matched deterministic government/tax/insurance signature.",
        )

    lender = detect_lender(text)
    if lender:
        tier, canonical = lender
        return RuleClassification(
            NON_REVENUE_MCA,
            0.99,
            f"Matched known lender alias for {canonical}.",
            lender_name=canonical,
            lender_tier=tier,
        )

    if str(direction).lower() == "credit" and re.search(POS_PROCESSOR_PATTERN, text, re.IGNORECASE):
        return RuleClassification(
            TRUE_REVENUE_POS,
            0.99,
            "Matched known payment processor / card settlement signature.",
        )

    return RuleClassification(
        None,
        0.0,
        "No deterministic rule matched; AI or human review is required.",
    )


def safe_fallback_category(category: str | None) -> str:
    return category or REVIEW_REQUIRED


def extract_transfer_reference(description: str) -> str | None:
    compact = re.sub(r"[^A-Z0-9#\-]", "", str(description or "").upper())
    match = re.search(r"TF\d{3,4}#?\d{3,4}[\-#]\d{3,4}", compact)
    return match.group(0) if match else None
