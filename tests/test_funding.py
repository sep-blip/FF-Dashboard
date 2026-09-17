from engine_v2.funding import FundingPolicy, calculate_funding_capacity


def test_funding_limit_is_minimum_of_policy_constraints():
    policy = FundingPolicy(
        revenue_multiple=0.8,
        max_total_debt_burden_pct=20,
        factor_rate=1.30,
        term_business_days=126,
    )
    result = calculate_funding_capacity(
        average_monthly_true_revenue=100000,
        existing_monthly_debt_service=10000,
        policy=policy,
    )

    assert result.max_by_revenue == 80000
    assert result.recommended_advance <= result.max_by_revenue
    assert result.projected_total_debt_ratio_pct <= 20.01


def test_absolute_cap_is_enforced():
    policy = FundingPolicy(
        revenue_multiple=2.0,
        max_total_debt_burden_pct=50,
        factor_rate=1.2,
        term_business_days=200,
        absolute_max_advance=25000,
    )
    result = calculate_funding_capacity(
        average_monthly_true_revenue=100000,
        existing_monthly_debt_service=0,
        policy=policy,
    )
    assert result.recommended_advance == 25000
