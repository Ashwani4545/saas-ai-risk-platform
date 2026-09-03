"""Risk prediction models.

Previous version trained on labels generated from a formula over pure
random noise, with no train/test split and no metrics printed anywhere -
so there was no way to tell if the model was any good, or even meaningfully
different from a coin flip. This version:
  - trains on the tenant-scoped, feature-driven labels from
    data/generate_features.py
  - holds out a test split and reports AUC/precision/recall/accuracy
  - writes those metrics to models/trained/metrics.json so they're checked
    in and visible, not just printed once during a training run
"""
import json
import os
from typing import Dict, Optional

import joblib
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, precision_score, recall_score, accuracy_score, f1_score

MODEL_DIR = "models/trained"
FEATURE_COLUMNS = [
    "recency",
    "frequency",
    "monetary",
    "account_age_days",
    "num_transactions",
    "avg_transaction_amount",
    "num_disputes",
    "credit_score",
]


class RiskModel:
    def __init__(self, model_version: str = "model_A"):
        self.model_version = model_version
        self.model = None

    def load(self):
        path = f"{MODEL_DIR}/{self.model_version}.joblib"
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"No trained model at {path}. Run `python -m models.risk_model` to train one first."
            )
        self.model = joblib.load(path)
        return self

    def predict(self, feature_vector: np.ndarray) -> Dict:
        if self.model is None:
            self.load()
        proba = self.model.predict_proba(feature_vector.reshape(1, -1))[0]
        risk_score = float(proba[1])
        return {
            "risk_score": risk_score,
            "risk_class": int(risk_score >= 0.5),
            "model_version": self.model_version,
        }


_models: Dict[str, RiskModel] = {}


def get_model(model_version: str = "model_A") -> RiskModel:
    if model_version not in _models:
        _models[model_version] = RiskModel(model_version).load()
    return _models[model_version]


def _evaluate(model, X_test, y_test) -> Dict[str, float]:
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]
    return {
        "auc": round(float(roc_auc_score(y_test, y_proba)), 4),
        "accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
        "precision": round(float(precision_score(y_test, y_pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_test, y_pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_test, y_pred, zero_division=0)), 4),
    }


def train_and_save_models(training_frame: Optional["pd.DataFrame"] = None) -> Dict[str, Dict]:
    from feature_store.feature_service import get_feature_store

    if training_frame is None:
        training_frame = get_feature_store().get_training_frame()

    if training_frame is None or len(training_frame) == 0:
        raise ValueError("No training data available - run data/generate_features.py first")

    X = training_frame[FEATURE_COLUMNS].values
    y = training_frame["risk_label"].values

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    os.makedirs(MODEL_DIR, exist_ok=True)
    all_metrics = {}

    model_a = RandomForestClassifier(n_estimators=200, max_depth=8, random_state=42, class_weight="balanced")
    model_a.fit(X_train, y_train)
    joblib.dump(model_a, f"{MODEL_DIR}/model_A.joblib")
    all_metrics["model_A"] = _evaluate(model_a, X_test, y_test)
    print(f"Trained and saved model_A - {all_metrics['model_A']}")

    model_b = GradientBoostingClassifier(n_estimators=150, max_depth=3, random_state=42)
    model_b.fit(X_train, y_train)
    joblib.dump(model_b, f"{MODEL_DIR}/model_B.joblib")
    all_metrics["model_B"] = _evaluate(model_b, X_test, y_test)
    print(f"Trained and saved model_B - {all_metrics['model_B']}")

    with open(f"{MODEL_DIR}/metrics.json", "w") as f:
        json.dump(all_metrics, f, indent=2)

    return all_metrics


if __name__ == "__main__":
    train_and_save_models()
