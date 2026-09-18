from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from .features import CATEGORICAL_FEATURES, NUMERIC_FEATURES


class PdModelNotReady(RuntimeError):
    pass


class PdModel:
    def __init__(self, artifact_dir: str | Path):
        artifact_dir = Path(artifact_dir)
        model_path = artifact_dir / "pd_model.joblib"
        metadata_path = artifact_dir / "pd_model_metadata.json"

        if not model_path.exists() or not metadata_path.exists():
            raise PdModelNotReady(
                f"PD model artifact is incomplete at {artifact_dir}."
            )

        self.pipeline = joblib.load(model_path)
        self.metadata = json.loads(
            metadata_path.read_text(encoding="utf-8")
        )

    def predict_pd(self, features: dict[str, Any]) -> float:
        missing = [
            feature
            for feature in NUMERIC_FEATURES + CATEGORICAL_FEATURES
            if feature not in features
        ]
        if missing:
            raise ValueError(
                "Missing PD model features: " + ", ".join(missing)
            )

        frame = pd.DataFrame(
            [
                {
                    feature: features[feature]
                    for feature in NUMERIC_FEATURES + CATEGORICAL_FEATURES
                }
            ]
        )
        probability = float(
            self.pipeline.predict_proba(frame)[0, 1]
        )
        return min(1.0, max(0.0, probability))

    def shap_explanation(
        self,
        features: dict[str, Any],
        *,
        top_n: int = 10,
    ) -> list[dict[str, float | str]]:
        import shap

        frame = pd.DataFrame(
            [
                {
                    feature: features[feature]
                    for feature in NUMERIC_FEATURES + CATEGORICAL_FEATURES
                }
            ]
        )
        preprocessor = self.pipeline.named_steps["preprocessor"]
        model = self.pipeline.named_steps["model"]
        transformed = preprocessor.transform(frame)
        feature_names = preprocessor.get_feature_names_out()

        explainer = shap.TreeExplainer(model)
        values = explainer.shap_values(transformed)
        row_values = values[0]

        ranked = sorted(
            zip(feature_names, row_values),
            key=lambda item: abs(float(item[1])),
            reverse=True,
        )[:top_n]

        return [
            {
                "feature": str(feature),
                "shap_value": float(value),
            }
            for feature, value in ranked
        ]
