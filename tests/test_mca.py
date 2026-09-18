from datetime import date

from engine_v2.mca import McaDebit, aggregate_positions, infer_frequency, monthly_equivalent


def test_weekly_frequency_inference():
    dates = [date(2026, 9, 1), date(2026, 9, 8), date(2026, 9, 15)]
    assert infer_frequency(dates) == "Weekly"


def test_monthly_equivalent_weekly():
    assert monthly_equivalent(1000, "Weekly") == 4330.0


def test_position_aggregation():
    rows = [
        McaDebit(
            transaction_date=date(2026, 9, 1),
            description="GREENBOX",
            lender="GREENBOX",
            tier="Premium",
            payment_amount=500,
        ),
        McaDebit(
            transaction_date=date(2026, 9, 2),
            description="GREENBOX",
            lender="GREENBOX",
            tier="Premium",
            payment_amount=500,
        ),
    ]
    positions = aggregate_positions(rows)
    assert len(positions) == 1
    assert positions[0].frequency == "Daily"
    assert positions[0].monthly_payment == 10500.0
