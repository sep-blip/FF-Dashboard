from dataclasses import dataclass

from engine_v2.features import calculate_underwriting_features


@dataclass
class Tx:
    date: str
    amount: float
    direction: str
    category: str
    description: str


def test_underwriting_features_use_selected_baseline_months():
    transactions = [
        Tx(
            "2026-07-01",
            10000,
            "credit",
            "True Revenue - Customer Payment / Cheque",
            "CUSTOMER A",
        ),
        Tx(
            "2026-08-01",
            12000,
            "credit",
            "True Revenue - Customer Payment / Cheque",
            "CUSTOMER A",
        ),
        Tx(
            "2026-08-02",
            3000,
            "credit",
            "True Revenue - Customer Payment / Cheque",
            "CUSTOMER B",
        ),
        Tx(
            "2026-08-03",
            500,
            "debit",
            "Debit / Cash Outflow",
            "NSF RETURNED ITEM",
        ),
    ]

    result = calculate_underwriting_features(
        transactions=transactions,
        monthly_true_revenue={
            "2026-07": 10000,
            "2026-08": 15000,
            "2026-09": 8000,
        },
        baseline_months=["2026-07", "2026-08"],
        average_monthly_true_revenue=12500,
        mca_position_count=1,
        monthly_mca_debt_service=2500,
    )

    assert result.revenue_trend_pct == 50.0
    assert result.average_deposit_count == 2
    assert result.returned_payment_count == 1
    assert result.mca_burden_pct == 20.0
    assert result.revenue_coverage_ratio == 5.0
