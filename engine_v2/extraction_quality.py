from __future__ import annotations

from pydantic import BaseModel, Field

from .models import ReconciliationStatus


class ExtractionQuality(BaseModel):
    score: int = Field(ge=0, le=100)
    status: str
    extraction_mode: str
    bank_id: str | None = None
    transaction_count: int = Field(ge=0)
    pages_with_positioned_words: int = Field(ge=0)
    page_count: int = Field(ge=0)
    factors: dict[str, int] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


def assess_extraction_quality(
    *,
    extraction_mode: str,
    bank_id: str | None,
    page_count: int,
    pages_with_positioned_words: int,
    transaction_count: int,
    period_detected: bool,
    credit_anchor_detected: bool,
    balances_detected: bool,
    reconciliation_status: str | None,
) -> ExtractionQuality:
    """Score extraction reliability from observable controls.

    This is not an LLM self-confidence score. It is a deterministic quality
    score based on document coverage, extraction evidence and reconciliation.
    """

    score = 0
    factors: dict[str, int] = {}
    warnings: list[str] = []

    factor = 10 if bank_id else 4
    factors["bank_template_identified"] = factor
    score += factor
    if not bank_id:
        warnings.append("Bank template was not identified.")

    if page_count > 0:
        positioned_ratio = pages_with_positioned_words / page_count
    else:
        positioned_ratio = 0.0

    factor = round(25 * min(1.0, positioned_ratio))
    factors["positioned_page_coverage"] = factor
    score += factor
    if positioned_ratio < 0.8:
        warnings.append(
            f"Positioned text was available on only "
            f"{pages_with_positioned_words}/{page_count or 0} pages."
        )

    if transaction_count >= 10:
        factor = 15
    elif transaction_count > 0:
        factor = 8
    else:
        factor = 0
        warnings.append("No transactions were extracted.")
    factors["transaction_rows"] = factor
    score += factor

    factor = 10 if period_detected else 0
    factors["statement_period"] = factor
    score += factor
    if not period_detected:
        warnings.append("Statement period could not be verified.")

    factor = 10 if credit_anchor_detected else 0
    factors["credit_anchor"] = factor
    score += factor
    if not credit_anchor_detected:
        warnings.append("No independent credit/deposit anchor was detected.")

    factor = 10 if balances_detected else 0
    factors["opening_closing_balances"] = factor
    score += factor
    if not balances_detected:
        warnings.append("Opening and closing balances were not both detected.")

    if reconciliation_status == ReconciliationStatus.PASS.value:
        factor = 20
    elif reconciliation_status == ReconciliationStatus.WARNING.value:
        factor = 8
        warnings.append("Ledger reconciliation returned a warning.")
    else:
        factor = 0
        if reconciliation_status == ReconciliationStatus.FAIL.value:
            warnings.append("Ledger reconciliation failed.")
        else:
            warnings.append("Full ledger reconciliation was not available.")
    factors["reconciliation"] = factor
    score += factor

    score = max(0, min(100, score))
    status = "HIGH" if score >= 85 else "MODERATE" if score >= 65 else "LOW"

    mode_upper = extraction_mode.upper()
    if (
        mode_upper.startswith("OCR")
        or "VISION" in mode_upper
    ) and status == "HIGH":
        status = "MODERATE"
        warnings.append(
            "OCR/vision-derived extraction is capped at MODERATE until "
            "validated against native positioned text or a private golden "
            "statement corpus."
        )

    return ExtractionQuality(
        score=score,
        status=status,
        extraction_mode=extraction_mode,
        bank_id=bank_id,
        transaction_count=transaction_count,
        pages_with_positioned_words=pages_with_positioned_words,
        page_count=page_count,
        factors=factors,
        warnings=warnings,
    )
