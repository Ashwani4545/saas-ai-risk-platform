"""Tests for the Risk Model"""
import numpy as np

from models.risk_model import RiskModel, get_model, FEATURE_COLUMNS


class TestRiskModel:
    def test_model_loads_from_disk(self):
        """conftest trains and saves both models before the test session runs"""
        model = RiskModel("model_A").load()
        assert model.model is not None

    def test_missing_model_raises_clear_error(self):
        import pytest

        with pytest.raises(FileNotFoundError):
            RiskModel("model_nonexistent").load()

    def test_predict_returns_valid_shape(self):
        model = RiskModel("model_A").load()
        features = np.random.default_rng(1).normal(size=len(FEATURE_COLUMNS))

        result = model.predict(features)

        assert 0 <= result["risk_score"] <= 1
        assert result["risk_class"] in (0, 1)
        assert result["model_version"] == "model_A"

    def test_get_model_caching(self):
        model1 = get_model("model_A")
        model2 = get_model("model_A")
        assert model1 is model2


class TestABTestModels:
    def test_different_models_for_ab(self):
        model_a = RiskModel("model_A").load()
        model_b = RiskModel("model_B").load()

        assert type(model_a.model).__name__ == "RandomForestClassifier"
        assert type(model_b.model).__name__ == "GradientBoostingClassifier"


class TestTrainingMetrics:
    def test_metrics_file_written(self):
        import json
        import os

        assert os.path.exists("models/trained/metrics.json")
        with open("models/trained/metrics.json") as f:
            metrics = json.load(f)

        for version in ("model_A", "model_B"):
            assert 0.5 <= metrics[version]["auc"] <= 1.0, "model should beat random guessing"
