from engine_v2.scorecard import MAX_SCORE, ScorecardInputs, calculate_scorecard


def _strong_inputs(**overrides):
    values = dict(
        average_monthly_true_revenue=160000,
        revenue_trend_pct=20,
        average_deposit_count=50,
        revenue_volatility_pct=5,
        average_daily_balance=20000,
        mca_position_count=0,
        mca_burden_pct=0,
        borrowing_velocity="0 in 90 Days",
        returned_ach_or_missed_payments=0,
        negative_days=0,
        time_in_business_months=100,
        industry_score=8,
        seasonality_score=6,
        credit_score=780,
        public_records="Clean",
        bank_verification="Bank Connect",
        revenue_concentration_pct=10,
    )
    values.update(overrides)
    return ScorecardInputs(**values)


def test_max_score_is_explicit_and_reachable():
    result = calculate_scorecard(_strong_inputs())
    assert result.score == MAX_SCORE == 93
    assert result.grade == "A+"
    assert not result.hard_stop


def test_low_revenue_is_hard_stop():
    result = calculate_scorecard(
        _strong_inputs(average_monthly_true_revenue=9000)
    )
    assert result.hard_stop
    assert result.score == 0
    assert result.revenue_advance_multiple == 0


def test_suspected_fraud_is_hard_stop():
    result = calculate_scorecard(_strong_inputs(suspected_fraud=True))
    assert result.hard_stop
    assert any("fraud" in reason.lower() for reason in result.hard_stop_reasons)
