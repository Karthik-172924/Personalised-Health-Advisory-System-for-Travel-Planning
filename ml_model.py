from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
MODEL_PATH = ROOT / "models" / "travel_risk_model.joblib"

FEATURE_ORDER = [
    "temperature",
    "humidity",
    "wind_speed",
    "aqi",
    "altitude",
    "age",
    "bmi",
    "smoking",
    "alcohol",
    "severity",
]

SEVERITY_MAP = {"low": 0, "moderate": 1, "high": 2}
BOOLEAN_MAP = {"No": 0, "Yes": 1}
FEATURE_BOUNDS = {
    "temperature": (0.0, 45.0),
    "humidity": (20.0, 100.0),
    "wind_speed": (0.0, 40.0),
    "aqi": (10.0, 300.0),
    "altitude": (0.0, 4000.0),
    "age": (5.0, 80.0),
    "bmi": (16.0, 35.0),
    "smoking": (0.0, 1.0),
    "alcohol": (0.0, 1.0),
    "severity": (0.0, 2.0),
}


@lru_cache(maxsize=1)
def load_model():
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Missing trained model at {MODEL_PATH}. Run generate_dataset.py and train_risk_model.py first."
        )
    model = joblib.load(MODEL_PATH)
    if not hasattr(model, "predict"):
        raise TypeError("Loaded risk model does not support predict().")
    return model


def _encode_features(features: dict) -> np.ndarray:
    severity = str(features.get("severity", "low")).strip().lower()
    smoking = "Yes" if features.get("smoking") == "Yes" else "No"
    alcohol = "Yes" if features.get("alcohol") == "Yes" else "No"

    return np.array(
        [
            float(features.get("temperature", 25)),
            float(features.get("humidity", 50)),
            float(features.get("wind_speed", 10)),
            float(features.get("aqi", 50)),
            float(features.get("altitude", 0)),
            int(features.get("age", 30)),
            float(features.get("bmi", 22)),
            BOOLEAN_MAP[smoking],
            BOOLEAN_MAP[alcohol],
            SEVERITY_MAP.get(severity, 0),
        ],
        dtype=float,
    )


def _build_model_frame(encoded: np.ndarray) -> pd.DataFrame:
    return pd.DataFrame([encoded], columns=FEATURE_ORDER)


def _normalize_feature(name: str, value: float) -> float:
    lower, upper = FEATURE_BOUNDS[name]
    if upper <= lower:
        return 0.0
    return float(np.clip((value - lower) / (upper - lower), 0.0, 1.0))


def _build_breakdown(encoded: np.ndarray, predicted_score: float, model) -> dict:
    importances = getattr(model, "feature_importances_", None)
    if importances is None or len(importances) != len(FEATURE_ORDER):
        importances = np.ones(len(FEATURE_ORDER), dtype=float)
    else:
        importances = np.asarray(importances, dtype=float)

    normalized = np.array(
        [
            _normalize_feature(name, value)
            for name, value in zip(FEATURE_ORDER, encoded, strict=False)
        ],
        dtype=float,
    )

    weighted_signal = normalized * importances
    score_scale = float(np.clip(predicted_score / 10.0, 0.0, 1.0))

    group_indices = {
        "environment": [2, 3, 4],
        "medical": [5, 6, 9],
        "lifestyle": [7, 8],
        "climate": [0, 1],
    }

    breakdown = {}
    for label, indices in group_indices.items():
        max_signal = float(importances[indices].sum())
        raw_signal = float(weighted_signal[indices].sum())
        if max_signal <= 0:
            value = 0.0
        else:
            value = (raw_signal / max_signal) * 10.0 * score_scale
        breakdown[label] = round(float(np.clip(value, 0.0, 10.0)), 1)

    return breakdown


def predict_risk_level(features: dict) -> tuple[str, float, dict]:
    model = load_model()
    encoded = _encode_features(features)
    risk_score = round(float(model.predict(_build_model_frame(encoded))[0]), 1)
    risk_score = float(np.clip(risk_score, 0.0, 10.0))
    breakdown = _build_breakdown(encoded, risk_score, model)

    if risk_score <= 2:
        level = "Low"
    elif risk_score <= 5:
        level = "Moderate"
    elif risk_score <= 8:
        level = "High"
    else:
        level = "Critical"

    return level, risk_score, breakdown
