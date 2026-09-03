"""Shared test fixtures.

Uses a temp working directory per test session so tests never touch the
developer's real data/app.db, data/customer_features.parquet, or
models/trained/ - and sets a fixed JWT secret + fresh SQLite DB so auth
tests are deterministic and isolated from any real deployment.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-do-not-use-in-prod")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("KAFKA_ENABLED", "false")
os.environ.setdefault("SEED_DEMO_DATA", "true")

import pytest


@pytest.fixture(scope="session", autouse=True)
def _test_workspace(tmp_path_factory):
    # DATABASE_PATH/MLFLOW_TRACKING_URI default to relative paths ("data/app.db",
    # "sqlite:///mlflow.db") that are resolved lazily against cwd at connect
    # time, not at import time - so chdir'ing here (before any DB/MLflow call
    # happens) is enough to sandbox them in the temp workspace, with no need
    # to fight module-level env var caching in core.config.
    workspace = tmp_path_factory.mktemp("workspace")
    os.chdir(workspace)

    from core import db

    db.init_db()

    from data.generate_features import save_features

    save_features()

    from models.risk_model import train_and_save_models

    train_and_save_models()

    yield workspace
