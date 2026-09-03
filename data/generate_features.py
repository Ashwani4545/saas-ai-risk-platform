"""Generate synthetic-but-principled customer features for the feature store.

Previous version derived risk labels from a formula over pure Gaussian noise
(`np.random.randn`), so the "risk" the model learned wasn't tied to any of
the named features in a way a human could sanity-check. This version builds
each feature from a distribution appropriate to what it represents (RFM,
credit score, disputes) and derives risk from a weighted, documented
combination of those features plus noise - so the model is learning
something an interviewer can actually reason about, and it's evaluable with
real classification metrics (see models/risk_model.py).
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
import os

FEATURES_PATH = "data/customer_features.parquet"

# Every generated tenant gets its own slice of customers, so per-tenant
# scoping in the feature store and vector store has something real to enforce.
TENANTS = ["tenant_1", "tenant_2"]


def _risk_probability(recency, frequency, monetary, num_disputes, credit_score, account_age_days) -> np.ndarray:
    """Weighted, documented risk formula (not learned - this is the ground
    truth the model is trained to approximate). Higher recency (longer since
    last activity), more disputes, and lower credit score raise risk; higher
    frequency, monetary value, and account age lower it."""
    z = (
        0.035 * recency
        - 0.05 * frequency
        - 0.0008 * monetary
        + 0.9 * num_disputes
        - 0.01 * (credit_score - 650)
        - 0.001 * account_age_days
    )
    return 1 / (1 + np.exp(-z))


def generate_customer_features(n_customers_per_tenant: int = 500, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    frames = []
    customer_id = 1

    for tenant_id in TENANTS:
        n = n_customers_per_tenant
        base_date = datetime.now(timezone.utc)
        timestamps = [base_date - timedelta(days=int(rng.integers(0, 30))) for _ in range(n)]

        recency = rng.exponential(10, n)
        frequency = rng.poisson(5, n) + 1
        monetary = rng.lognormal(5, 1, n)
        account_age_days = rng.integers(30, 1000, n)
        num_transactions = rng.poisson(20, n)
        avg_transaction_amount = monetary / np.maximum(num_transactions, 1)
        num_disputes = rng.poisson(0.4, n)
        credit_score = np.clip(rng.normal(700, 60, n), 300, 850)

        risk_prob = _risk_probability(recency, frequency, monetary, num_disputes, credit_score, account_age_days)
        risk_label = (rng.random(n) < risk_prob).astype(int)

        frames.append(
            pd.DataFrame(
                {
                    "customer_id": range(customer_id, customer_id + n),
                    "tenant_id": tenant_id,
                    "event_timestamp": timestamps,
                    "recency": recency,
                    "frequency": frequency,
                    "monetary": monetary,
                    "account_age_days": account_age_days,
                    "num_transactions": num_transactions,
                    "avg_transaction_amount": avg_transaction_amount,
                    "num_disputes": num_disputes,
                    "credit_score": credit_score,
                    "risk_label": risk_label,
                }
            )
        )
        customer_id += n

    return pd.concat(frames, ignore_index=True)


def save_features():
    os.makedirs("data", exist_ok=True)
    df = generate_customer_features()
    df.to_parquet(FEATURES_PATH, index=False)
    print(f"Saved {len(df)} customer features across {len(TENANTS)} tenants to {FEATURES_PATH}")
    print(f"Overall risk rate: {df['risk_label'].mean():.2%}")
    return df


if __name__ == "__main__":
    save_features()
