"""Fraud-risk model for the product authenticity domain.

Deliberately mirrors models/risk_model.py's interface (load-from-disk,
.predict() -> {risk_score, risk_class}, real train/test evaluation written
to a metrics.json) - same platform pattern applied to a second domain,
which is the actual point of building this as an extension of the existing
platform rather than a separate one-off project.
"""
import json
import os
from typing import Dict

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, precision_score, recall_score, accuracy_score, f1_score

MODEL_DIR = "models/trained"
MODEL_PATH = f"{MODEL_DIR}/fraud_model.joblib"
METRICS_PATH = f"{MODEL_DIR}/fraud_metrics.json"

FEATURE_COLUMNS = [
    "scan_count",
    "unique_locations",
    "max_travel_speed_kmh",
    "min_seconds_between_scans",
    "scans_last_hour",
]


class FraudRiskModel:
    def __init__(self):
        self.model = None

    def load(self):
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(
                f"No trained fraud model at {MODEL_PATH}. Run `python -m product_auth.fraud_model` first."
            )
        self.model = joblib.load(MODEL_PATH)
        return self

    def predict(self, feature_vector: np.ndarray) -> Dict:
        if self.model is None:
            self.load()
        proba = self.model.predict_proba(feature_vector.reshape(1, -1))[0]
        risk_score = float(proba[1])
        return {"risk_score": risk_score, "risk_class": int(risk_score >= 0.5)}


_model: FraudRiskModel = None


def get_fraud_model() -> FraudRiskModel:
    global _model
    if _model is None:
        _model = FraudRiskModel().load()
    return _model


def train_and_save_fraud_model(training_frame=None) -> Dict[str, float]:
    from product_auth.data_generator import TRAINING_DATA_PATH
    import pandas as pd

    if training_frame is None:
        if not os.path.exists(TRAINING_DATA_PATH):
            raise FileNotFoundError(
                f"No training data at {TRAINING_DATA_PATH}. Run `python -m product_auth.data_generator` first."
            )
        training_frame = pd.read_parquet(TRAINING_DATA_PATH)

    X = training_frame[FEATURE_COLUMNS].values
    y = training_frame["fraud_label"].values

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    os.makedirs(MODEL_DIR, exist_ok=True)
    model = RandomForestClassifier(n_estimators=200, max_depth=6, random_state=42, class_weight="balanced")
    model.fit(X_train, y_train)
    joblib.dump(model, MODEL_PATH)

    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]
    metrics = {
        "auc": round(float(roc_auc_score(y_test, y_proba)), 4),
        "accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
        "precision": round(float(precision_score(y_test, y_pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_test, y_pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_test, y_pred, zero_division=0)), 4),
    }
    with open(METRICS_PATH, "w") as f:
        json.dump(metrics, f, indent=2)

    print(f"Trained and saved fraud_model - {metrics}")
    return metrics


if __name__ == "__main__":
    from core import db

    db.init_db()
    train_and_save_fraud_model()
