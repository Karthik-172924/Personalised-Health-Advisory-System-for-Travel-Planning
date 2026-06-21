from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parent
DATASET_PATH = ROOT / "travel_health_dataset.csv"
MODEL_PATH = ROOT / "models" / "travel_risk_model.joblib"
FEATURE_COLUMNS = [
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


def load_dataset(path: Path = DATASET_PATH) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"Dataset not found at {path}. Run generate_dataset.py before training."
        )

    df = pd.read_csv(path)
    required = FEATURE_COLUMNS + ["risk_score"]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"Dataset is missing required columns: {', '.join(missing)}")
    return df[required].copy()


def encode_features(df: pd.DataFrame) -> pd.DataFrame:
    encoded = df.copy()
    encoded["smoking"] = encoded["smoking"].map({"No": 0, "Yes": 1})
    encoded["alcohol"] = encoded["alcohol"].map({"No": 0, "Yes": 1})
    encoded["severity"] = encoded["severity"].str.lower().map({"low": 0, "moderate": 1, "high": 2})
    if encoded[["smoking", "alcohol", "severity"]].isna().any().any():
        raise ValueError("Dataset contains unsupported categorical values.")
    return encoded


def train_model() -> RandomForestRegressor:
    df = encode_features(load_dataset())
    X = df[FEATURE_COLUMNS]
    y = df["risk_score"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    model = RandomForestRegressor(
        n_estimators=100,
        max_depth=10,
        random_state=42,
    )
    model.fit(X_train, y_train)

    train_score = model.score(X_train, y_train)
    test_score = model.score(X_test, y_test)

    joblib.dump(model, MODEL_PATH)

    print(f"Training rows: {len(X_train)}")
    print(f"Test rows: {len(X_test)}")
    print(f"Train R^2: {train_score:.4f}")
    print(f"Test R^2: {test_score:.4f}")
    print(f"Model saved to {MODEL_PATH}")
    return model


if __name__ == "__main__":
    train_model()
