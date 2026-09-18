# Probability of Default model

The repository now contains the training and inference pipeline for a future
application-level probability-of-default (PD) model. It intentionally does
not contain a fake pre-trained production model.

## Target

The target column is default_flag. It must represent an observed outcome with
an agreed performance window and default definition. That definition must be
fixed before production training.

## Required training columns

Identifiers:
- application_id
- as_of_date

Numeric features:
- average_monthly_true_revenue
- revenue_trend_pct
- revenue_volatility_pct
- average_deposit_count
- revenue_concentration_pct
- average_daily_balance
- negative_days
- nsf_count
- mca_position_count
- monthly_mca_debt_service
- total_debt_ratio_pct
- credit_score
- revolving_utilization_pct
- active_collections_count
- time_in_business_months

Categorical features:
- industry_code
- bank_verification
- borrowing_velocity

Target:
- default_flag (0/1)

## Training

Install the optional ML dependencies with:

    pip install -r requirements-ml.txt

Then train a candidate artifact with:

    python -m ml.train_pd_model data/training.csv --output-dir artifacts/pd_model

The training job records ROC AUC, average precision, Brier score, the feature
contract, and artifact metadata.

## Production gate

Every generated artifact is marked production_approved = false. Before a model
is allowed to influence a funding decision it should pass:

1. outcome-definition review;
2. leakage testing;
3. out-of-time validation;
4. probability-calibration review;
5. stability and drift analysis;
6. underwriting and compliance review;
7. documented approval and model-version registration.

The deterministic policy and funding engine remains the final limit
calculator. The PD model is an input to policy, not an unrestricted
loan-amount generator.
