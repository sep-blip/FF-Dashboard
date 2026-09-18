import pytest

from engine_v2.constants import (
    NON_REVENUE_INTERNAL,
    TRUE_REVENUE_CUSTOMER,
)
from engine_v2.review import (
    ReviewedTransaction,
    TransactionOverride,
    recalculate_after_review,
)


def _transactions():
    return [
        ReviewedTransaction(
            transaction_id="t1",
            date="2026-08-01",
            amount=10000,
            direction="credit",
            category="Review Required - Unidentified / Unusual Deposit",
            needs_review=True,
        ),
        ReviewedTransaction(
            transaction_id="t2",
            date="2026-08-02",
            amount=5000,
            direction="credit",
            category=NON_REVENUE_INTERNAL,
            needs_review=False,
        ),
    ]


def test_override_recalculates_true_revenue_and_readiness():
    result = recalculate_after_review(
        transactions=_transactions(),
        overrides=[
            TransactionOverride(
                transaction_id="t1",
                category=TRUE_REVENUE_CUSTOMER,
                reason="Verified invoice payment",
            )
        ],
        coverage_status_by_month={"2026-08": "COMPLETE"},
        monthly_debt_service_by_lender={},
        readiness_checks={
            "documents": "PASS",
            "ledger": "PASS",
            "extraction_quality": "PASS",
            "reconciliation": "PASS",
            "integrity": "PASS",
            "coverage": "PASS",
            "classification": "REVIEW",
            "revenue_baseline": "PASS",
        },
    )

    assert result.monthly_true_revenue["2026-08"] == 10000
    assert result.remaining_review_count == 0
    assert result.readiness_status == "READY"
    assert result.automated_offer_allowed


def test_override_rejects_unknown_category():
    with pytest.raises(ValueError):
        recalculate_after_review(
            transactions=_transactions(),
            overrides=[
                TransactionOverride(
                    transaction_id="t1",
                    category="Made Up Category",
                    reason="bad",
                )
            ],
            coverage_status_by_month={"2026-08": "COMPLETE"},
            monthly_debt_service_by_lender={},
        )
