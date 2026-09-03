"""Feature store service for retrieving customer features.

Every read is scoped by (tenant_id, customer_id) - not customer_id alone -
so tenant A can no longer fetch tenant B's customer features by guessing an
ID. There's no Feast dependency here: the previous repo listed feast in
requirements.txt and had a feature_repo.py defining entities, but nothing in
the running app ever called into Feast - it was decorative. This is an
honest, small, pandas-backed feature store instead. Swapping it for a real
Feast/Redis online store later is a drop-in change behind this same
interface, and is called out as a next step in the README.
"""
import pandas as pd
import numpy as np
import os

FEATURES_PATH = "data/customer_features.parquet"

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


class FeatureStoreService:
    def __init__(self):
        self._features_df = None
        self._load_features()

    def _load_features(self):
        if os.path.exists(FEATURES_PATH):
            self._features_df = pd.read_parquet(FEATURES_PATH)
        else:
            self._features_df = pd.DataFrame(columns=["customer_id", "tenant_id", "event_timestamp"] + FEATURE_COLUMNS)

    def get_features(self, customer_id: int, tenant_id: str) -> dict:
        """Get features for a customer, scoped to the requesting tenant."""
        if self._features_df is None or len(self._features_df) == 0:
            return self._get_default_features(customer_id)

        customer_data = self._features_df[
            (self._features_df["customer_id"] == customer_id) & (self._features_df["tenant_id"] == tenant_id)
        ]

        if len(customer_data) == 0:
            # Either an unknown customer, or a real customer that belongs to
            # a different tenant - either way we don't leak it, we just
            # return deterministic defaults for this tenant's view.
            return self._get_default_features(customer_id)

        row = customer_data.iloc[0]
        return {
            "recency": float(row["recency"]),
            "frequency": float(row["frequency"]),
            "monetary": float(row["monetary"]),
            "account_age_days": int(row["account_age_days"]),
            "num_transactions": int(row["num_transactions"]),
            "avg_transaction_amount": float(row["avg_transaction_amount"]),
            "num_disputes": int(row["num_disputes"]),
            "credit_score": float(row["credit_score"]),
        }

    def _get_default_features(self, customer_id: int) -> dict:
        rng = np.random.default_rng(customer_id)
        return {
            "recency": float(rng.exponential(10)),
            "frequency": float(rng.poisson(5) + 1),
            "monetary": float(rng.lognormal(5, 1)),
            "account_age_days": int(rng.integers(30, 365)),
            "num_transactions": int(rng.poisson(20)),
            "avg_transaction_amount": float(rng.lognormal(4, 0.5)),
            "num_disputes": int(rng.poisson(0.5)),
            "credit_score": float(np.clip(rng.normal(700, 50), 300, 850)),
        }

    def get_feature_vector(self, customer_id: int, tenant_id: str) -> np.ndarray:
        features = self.get_features(customer_id, tenant_id)
        return np.array([features[col] for col in FEATURE_COLUMNS])

    def get_training_frame(self) -> pd.DataFrame:
        """All tenants' features + labels, for offline model training only
        (never exposed through the API)."""
        return self._features_df


_feature_store = None


def get_feature_store() -> FeatureStoreService:
    global _feature_store
    if _feature_store is None:
        _feature_store = FeatureStoreService()
    return _feature_store
