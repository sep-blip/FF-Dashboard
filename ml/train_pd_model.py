from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBClassifier

from .features import (
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    TARGET_COLUMN,
    validate_training_dataframe,
)


def build_pipeline(*, random_state: int = 42) -> Pipeline:
    preprocessor = ColumnTransformer(
        transformers=[
            ("numeric", "passthrough", NUMERIC_FEATURES),
            (
                "categorical",
                OneHotEncoder(
                    handle_unknown="ignore",
                    sparse_output=False,
                ),
                CATEGORICAL_FEATURES,
            ),
        ],
        remainder="drop",
        verbose_feature_names_out=False,
    )

    model = XGBClassifier(
        n_estimators=400,
        max_depth=4,
        learning_rate=0.04,
        subsample=0.85,
        colsample_bytree=0.85,
        objective="binary:logistic",
        eval_metric="logloss",
        random_state=random_state,
        n_jobs=4,
    )

    return Pipeline(
        [
            ("preprocessor", preprocessor),
            ("model", model),
        ]
    )


def train(
    *,
    dataset_path: Path,
    output_dir: Path,
    random_state: int = 42,
) -> dict:
    df = pd.read_csv(dataset_path)
    validation = validate_training_dataframe(df)
    if not validation.valid:
        raise ValueError(
            "Training-data validation failed: "
            + " | ".join(validation.errors)
        )

    X = df[NUMERIC_FEATURES + CATEGORICAL_FEATURES].copy()
    y = df[TARGET_COLUMN].astype(int)

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.25,
        stratify=y,
        random_state=random_state,
    )

    pipeline = build_pipeline(random_state=random_state)
    pipeline.fit(X_train, y_train)

    probabilities = pipeline.predict_proba(X_test)[:, 1]
    metrics = {
        "roc_auc": float(roc_auc_score(y_test, probabilities)),
        "average_precision": float(
            average_precision_score(y_test, probabilities)
        ),
        "brier_score": float(brier_score_loss(y_test, probabilities)),
        "test_rows": int(len(y_test)),
        "test_defaults": int(y_test.sum()),
        "training_rows": int(len(y_train)),
        "training_defaults": int(y_train.sum()),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    model_path = output_dir / "pd_model.joblib"
    metadata_path = output_dir / "pd_model_metadata.json"

    joblib.dump(pipeline, model_path)

    metadata = {
        "model_type": "XGBClassifier",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "target": TARGET_COLUMN,
        "numeric_features": NUMERIC_FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
        "metrics": metrics,
        "random_state": random_state,
        "training_dataset": str(dataset_path),
        "production_approved": False,
        "approval_note": (
            "Training creates a candidate artifact only. Production approval "
            "requires out-of-time validation, calibration review, leakage checks, "
            "fairness/compliance review, and underwriting sign-off."
        ),
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )

    return {
        "model_path": str(model_path),
        "metadata_path": str(metadata_path),
        "metrics": metrics,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/pd_model"),
    )
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()

    result = train(
        dataset_path=args.dataset,
        output_dir=args.output_dir,
        random_state=args.random_state,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
