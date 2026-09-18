from __future__ import annotations

from dataclasses import dataclass

NUMERIC_FEATURES = [
    "average_monthly_true_revenue",
    "revenue_trend_pct",
    "revenue_volatility_pct",
    "average_deposit_count",
    "revenue_concentration_pct",
    "average_daily_balance",
    "negative_days",
    "nsf_count",
    "mca_position_count",
    "monthly_mca_debt_service",
    "total_debt_ratio_pct",
    "credit_score",
    "revolving_utilization_pct",
    "active_collections_count",
    "time_in_business_months",
]

CATEGORICAL_FEATURES = [
    "industry_code",
    "bank_verification",
    "borrowing_velocity",
]

TARGET_COLUMN = "default_flag"
ID_COLUMNS = ["application_id", "as_of_date"]


@dataclass(frozen=True)
class TrainingDataValidation:
    valid: bool
    errors: tuple[str, ...]
    row_count: int
    default_count: int | None = None
    non_default_count: int | None = None


def required_columns() -> list[str]:
    return ID_COLUMNS + NUMERIC_FEATURES + CATEGORICAL_FEATURES + [TARGET_COLUMN]


def validate_training_dataframe(df) -> TrainingDataValidation:
    missing = [column for column in required_columns() if column not in df.columns]
    errors: list[str] = []
    if missing:
        errors.append("Missing required columns: " + ", ".join(missing))
        return TrainingDataValidation(
            valid=False,
            errors=tuple(errors),
            row_count=len(df),
        )

    target = df[TARGET_COLUMN]
    unique = set(target.dropna().astype(int).unique().tolist())
    if not unique.issubset({0, 1}):
        errors.append("default_flag must contain only 0/1 values.")
    if target.isna().any():
        errors.append("default_flag contains missing values.")

    default_count = int((target == 1).sum())
    non_default_count = int((target == 0).sum())
    if default_count < 25:
        errors.append(
            "Fewer than 25 default observations. This is insufficient for a "
            "credible production PD model."
        )
    if non_default_count < 25:
        errors.append(
            "Fewer than 25 non-default observations. This is insufficient for "
            "a credible production PD model."
        )

    return TrainingDataValidation(
        valid=not errors,
        errors=tuple(errors),
        row_count=len(df),
        default_count=default_count,
        non_default_count=non_default_count,
    )
