from engine_v2.classification import classify_by_rules, detect_lender
from engine_v2.constants import NON_REVENUE_INTERNAL, NON_REVENUE_MCA, TRUE_REVENUE_POS


def test_known_lender_is_non_revenue():
    result = classify_by_rules("ACH GREENBOX CAPITAL FUNDING")
    assert result.category == NON_REVENUE_MCA
    assert result.lender_name == "GREENBOX"


def test_internal_transfer_is_non_revenue():
    result = classify_by_rules("ONLINE TRANSFER TF 3978#1967-174")
    assert result.category == NON_REVENUE_INTERNAL


def test_processor_is_true_revenue():
    result = classify_by_rules("ACH CREDIT STRIPE PAYOUT")
    assert result.category == TRUE_REVENUE_POS


def test_unknown_stays_unclassified_for_ai_or_review():
    result = classify_by_rules("EFT CREDIT ABC HOLDINGS")
    assert result.category is None
    assert result.confidence == 0.0
