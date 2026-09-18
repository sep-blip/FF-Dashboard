from __future__ import annotations

from dataclasses import dataclass, field


POLICY_VERSION = "ff-scorecard-v1"
MAX_SCORE = 93


@dataclass(frozen=True)
class ScorecardInputs:
    average_monthly_true_revenue: float
    revenue_trend_pct: float
    average_deposit_count: int
    revenue_volatility_pct: float
    average_daily_balance: float
    mca_position_count: int
    mca_burden_pct: float
    borrowing_velocity: str
    returned_ach_or_missed_payments: int
    negative_days: int
    time_in_business_months: int
    industry_score: int
    seasonality_score: int
    credit_score: int
    public_records: str
    bank_verification: str
    revenue_concentration_pct: float
    suspected_fraud: bool = False
    severe_wash_transactions: bool = False
    active_lender_default: bool = False


@dataclass(frozen=True)
class ScorecardResult:
    policy_version: str
    score: int
    max_score: int
    grade: str
    risk_tier: str
    revenue_advance_multiple: float
    max_total_debt_burden_pct: float
    hard_stop: bool
    hard_stop_reasons: tuple[str, ...] = ()
    breakdown: dict[str, int] = field(default_factory=dict)


def _bounded_points(value: int, maximum: int) -> int:
    return max(0, min(int(value), maximum))


def calculate_scorecard(inputs: ScorecardInputs) -> ScorecardResult:
    hard_stop_reasons: list[str] = []
    if inputs.suspected_fraud:
        hard_stop_reasons.append("Suspected altered statements / fraud")
    if inputs.active_lender_default:
        hard_stop_reasons.append("Active lender default or collections")
    if inputs.severe_wash_transactions:
        hard_stop_reasons.append(
            "Evidence of structural wash transactions to cover debt"
        )
    if inputs.average_monthly_true_revenue < 10000:
        hard_stop_reasons.append(
            "Average true revenue is under the $10,000 policy minimum"
        )

    if hard_stop_reasons:
        return ScorecardResult(
            policy_version=POLICY_VERSION,
            score=0,
            max_score=MAX_SCORE,
            grade="E",
            risk_tier="Hard Stop",
            revenue_advance_multiple=0.0,
            max_total_debt_burden_pct=0.0,
            hard_stop=True,
            hard_stop_reasons=tuple(hard_stop_reasons),
            breakdown={},
        )

    rev = inputs.average_monthly_true_revenue
    pts_rev = (
        6 if rev >= 150000
        else 5 if rev >= 75000
        else 4 if rev >= 40000
        else 3 if rev >= 20000
        else 2 if rev >= 10000
        else 0
    )

    trend = inputs.revenue_trend_pct
    pts_trend = (
        6 if trend > 15
        else 5 if trend >= 5
        else 4 if trend >= -5
        else 2 if trend >= -10
        else 1 if trend >= -20
        else 0
    )

    count = inputs.average_deposit_count
    pts_count = (
        5 if count >= 40
        else 4 if count >= 20
        else 3 if count >= 10
        else 2 if count >= 5
        else 0
    )

    vol = inputs.revenue_volatility_pct
    pts_vol = (
        5 if vol <= 10
        else 4 if vol <= 20
        else 3 if vol <= 30
        else 2 if vol <= 40
        else 1 if vol <= 50
        else 0
    )

    adb_pct = (
        inputs.average_daily_balance / rev * 100
        if rev > 0 else 0
    )
    pts_adb = (
        5 if adb_pct >= 10
        else 4 if adb_pct >= 7
        else 3 if adb_pct >= 4
        else 2 if adb_pct >= 2
        else 1 if adb_pct >= 1
        else 0
    )

    positions = inputs.mca_position_count
    pts_positions = (
        6 if positions == 0
        else 5 if positions == 1
        else 3 if positions == 2
        else 1 if positions == 3
        else 0
    )

    burden = inputs.mca_burden_pct
    pts_burden = (
        10 if burden <= 8
        else 8 if burden <= 12
        else 6 if burden <= 16
        else 4 if burden <= 20
        else 2 if burden <= 25
        else 0
    )

    pts_velocity = (
        5 if inputs.borrowing_velocity == "0 in 90 Days"
        else 3 if inputs.borrowing_velocity == "1 in 90 Days"
        else 1
    )

    missed = inputs.returned_ach_or_missed_payments
    pts_payment = (
        4 if missed == 0
        else 3 if missed == 1
        else 2 if missed == 2
        else 1 if missed <= 4
        else 0
    )

    neg = inputs.negative_days
    pts_negative_days = (
        6 if neg == 0
        else 5 if neg <= 3
        else 3 if neg <= 6
        else 2 if neg <= 10
        else 1 if neg <= 15
        else 0
    )

    tib = inputs.time_in_business_months
    pts_tib = (
        6 if tib >= 84
        else 5 if tib >= 48
        else 4 if tib >= 24
        else 3 if tib >= 12
        else 1 if tib >= 6
        else 0
    )

    credit = inputs.credit_score
    pts_credit = (
        6 if credit >= 750
        else 5 if credit >= 700
        else 4 if credit >= 650
        else 3 if credit >= 600
        else 2 if credit >= 550
        else 1 if credit >= 500
        else 0
    )

    pts_public_records = (
        4 if inputs.public_records == "Clean"
        else 3 if inputs.public_records == "Minor"
        else 1 if inputs.public_records == "Moderate"
        else 0
    )

    pts_verification = (
        3 if inputs.bank_verification == "Bank Connect"
        else 2 if inputs.bank_verification == "Original PDF"
        else 1 if inputs.bank_verification == "Minor inconsistency"
        else 0
    )

    concentration = inputs.revenue_concentration_pct
    pts_concentration = (
        2 if concentration <= 20
        else 1 if concentration <= 35
        else 0
    )

    breakdown = {
        "true_revenue": pts_rev,
        "revenue_trend": pts_trend,
        "deposit_count": pts_count,
        "revenue_volatility": pts_vol,
        "average_daily_balance": pts_adb,
        "mca_positions": pts_positions,
        "mca_burden": pts_burden,
        "borrowing_velocity": pts_velocity,
        "payment_performance": pts_payment,
        "negative_days": pts_negative_days,
        "time_in_business": pts_tib,
        "industry": _bounded_points(inputs.industry_score, 8),
        "seasonality": _bounded_points(inputs.seasonality_score, 6),
        "credit_score": pts_credit,
        "public_records": pts_public_records,
        "bank_verification": pts_verification,
        "revenue_concentration": pts_concentration,
    }

    score = sum(breakdown.values())

    if score >= 90:
        grade, risk, advance, max_burden = "A+", "Prime MCA", 1.00, 18.0
    elif score >= 82:
        grade, risk, advance, max_burden = "A", "Strong", 0.85, 17.0
    elif score >= 74:
        grade, risk, advance, max_burden = "B", "Acceptable", 0.70, 15.0
    elif score >= 66:
        grade, risk, advance, max_burden = "C", "Elevated", 0.55, 13.0
    elif score >= 58:
        grade, risk, advance, max_burden = "D", "High", 0.35, 10.0
    else:
        grade, risk, advance, max_burden = "E", "High / Unacceptable", 0.00, 0.0

    return ScorecardResult(
        policy_version=POLICY_VERSION,
        score=score,
        max_score=MAX_SCORE,
        grade=grade,
        risk_tier=risk,
        revenue_advance_multiple=advance,
        max_total_debt_burden_pct=max_burden,
        hard_stop=False,
        hard_stop_reasons=(),
        breakdown=breakdown,
    )
