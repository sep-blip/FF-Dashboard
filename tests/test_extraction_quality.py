from engine_v2.extraction_quality import assess_extraction_quality


def test_reconciled_positioned_statement_can_be_high_confidence():
    result = assess_extraction_quality(
        extraction_mode="NATIVE_POSITIONED",
        bank_id="RBC",
        page_count=4,
        pages_with_positioned_words=4,
        transaction_count=35,
        period_detected=True,
        credit_anchor_detected=True,
        balances_detected=True,
        reconciliation_status="PASS",
    )
    assert result.score == 100
    assert result.status == "HIGH"


def test_unreconciled_unknown_template_is_low_confidence():
    result = assess_extraction_quality(
        extraction_mode="OCR_TEXT",
        bank_id=None,
        page_count=5,
        pages_with_positioned_words=0,
        transaction_count=0,
        period_detected=False,
        credit_anchor_detected=False,
        balances_detected=False,
        reconciliation_status="WARNING",
    )
    assert result.status == "LOW"
    assert result.warnings
