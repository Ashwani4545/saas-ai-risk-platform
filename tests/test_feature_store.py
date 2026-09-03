"""Tests for the tenant-scoped feature store"""
import numpy as np

from feature_store.feature_service import FeatureStoreService, get_feature_store


class TestFeatureStoreService:
    def test_get_features_returns_dict(self):
        service = FeatureStoreService()
        features = service.get_features(1, "tenant_1")

        assert isinstance(features, dict)
        assert "recency" in features
        assert "frequency" in features
        assert "monetary" in features

    def test_get_features_returns_floats(self):
        service = FeatureStoreService()
        features = service.get_features(1, "tenant_1")
        for key, value in features.items():
            assert isinstance(value, (int, float)), f"{key} should be numeric"

    def test_get_feature_vector(self):
        service = FeatureStoreService()
        vector = service.get_feature_vector(1, "tenant_1")
        assert isinstance(vector, np.ndarray)
        assert len(vector) == 8

    def test_default_features_for_unknown_customer(self):
        service = FeatureStoreService()
        features = service.get_features(999999, "tenant_1")
        assert isinstance(features, dict)
        assert len(features) == 8

    def test_singleton_pattern(self):
        store1 = get_feature_store()
        store2 = get_feature_store()
        assert store1 is store2


class TestFeatureStoreTenantIsolation:
    def test_real_customer_not_leaked_to_other_tenant(self):
        """conftest seeds customer_id=1 for tenant_1 via generate_features.
        Requesting the same ID under a different tenant must not return
        tenant_1's real data - it should fall back to deterministic defaults."""
        service = FeatureStoreService()

        as_owner = service.get_features(1, "tenant_1")
        as_other = service.get_features(1, "tenant_nonexistent")

        # A customer real to tenant_1 looks different (or at least isn't
        # guaranteed identical) when queried as a tenant that doesn't own it.
        assert as_owner != as_other or as_owner["credit_score"] != as_other["credit_score"]
