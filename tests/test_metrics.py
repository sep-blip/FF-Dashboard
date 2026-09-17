from engine_v2.metrics import (
    calculate_debt_ratios,
    project_partial_month,
    select_revenue_baseline,
)


def test_complete_months_drive_baseline_when_available():
    baseline = select_revenue_baseline(
        monthly_true_revenue={
            "2026-07": 100000,
            "2026-08": 120000,
            "2026-09": 60000,
        },
        coverage_status_by_month={
            "2026-07": "COMPLETE",
            "2026-08": "COMPLETE",
            "2026-09": "PARTIAL",
        },
    )
    assert baseline.average_monthly_true_revenue == 110000
    assert baseline.months_used == ("2026-07", "2026-08")
    assert baseline.partial_months_excluded == ("2026-09",)


def test_partial_projection_is_explicit_math():
    assert project_partial_month(
        observed_true_revenue=60000,
        observed_days=15,
        expected_days=30,
    ) == 120000


def test_debt_ratios_use_monthly_consistent_basis():
    result = calculate_debt_ratios(
        average_monthly_true_revenue=100000,
        monthly_debt_service_by_lender={"A": 5000, "B": 7500},
    )
    assert result.individual_ratios_pct["A"] == 5.0
    assert result.individual_ratios_pct["B"] == 7.5
    assert result.total_debt_ratio_pct == 12.5
