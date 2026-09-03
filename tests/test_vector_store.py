"""Tests for the per-tenant vector store"""
import numpy as np

from vector_store.faiss_store import VectorStore, get_vector_store


class TestVectorStore:
    def test_add_embedding(self):
        store = VectorStore(tenant_id="t_add", dimension=8)
        embedding = np.random.randn(8).astype("float32")

        idx = store.add_customer_embedding(1, embedding)

        assert idx == 0
        assert store.total_embeddings == 1

    def test_add_multiple_embeddings(self):
        store = VectorStore(tenant_id="t_multi", dimension=8)
        for i in range(10):
            store.add_customer_embedding(i, np.random.randn(8).astype("float32"))
        assert store.total_embeddings == 10

    def test_search_similar(self):
        store = VectorStore(tenant_id="t_search", dimension=8)
        base = np.array([1, 0, 0, 0, 0, 0, 0, 0], dtype="float32")
        store.add_customer_embedding(1, base)
        store.add_customer_embedding(2, np.array([0.9, 0.1, 0, 0, 0, 0, 0, 0], dtype="float32"))
        store.add_customer_embedding(3, np.array([0, 0, 0, 0, 0, 0, 0, 1], dtype="float32"))

        results = store.search_similar_customers(base, k=2)

        assert len(results) <= 2
        assert results[0]["customer_id"] == 1

    def test_search_with_exclusion(self):
        store = VectorStore(tenant_id="t_excl", dimension=8)
        base = np.array([1, 0, 0, 0, 0, 0, 0, 0], dtype="float32")
        store.add_customer_embedding(1, base)
        store.add_customer_embedding(2, np.array([0.9, 0.1, 0, 0, 0, 0, 0, 0], dtype="float32"))

        results = store.search_similar_customers(base, k=2, exclude_customer_id=1)

        assert 1 not in [r["customer_id"] for r in results]

    def test_get_customer_embedding(self):
        store = VectorStore(tenant_id="t_get", dimension=8)
        embedding = np.array([1, 2, 3, 4, 5, 6, 7, 8], dtype="float32")
        store.add_customer_embedding(42, embedding)

        retrieved = store.get_customer_embedding(42)

        assert retrieved is not None
        np.testing.assert_array_almost_equal(retrieved, embedding)

    def test_get_nonexistent_embedding(self):
        store = VectorStore(tenant_id="t_none", dimension=8)
        assert store.get_customer_embedding(999) is None


class TestTenantIsolation:
    def test_tenants_get_independent_stores(self):
        store_a = get_vector_store("tenant_iso_a")
        store_b = get_vector_store("tenant_iso_b")

        store_a.add_customer_embedding(1, np.array([1, 0, 0, 0, 0, 0, 0, 0], dtype="float32"))

        assert store_a.total_embeddings >= 1
        # customer 1 in tenant A must not be visible from tenant B's store
        assert store_b.get_customer_embedding(1) is None

    def test_get_vector_store_returns_same_instance_per_tenant(self):
        store1 = get_vector_store("tenant_iso_same")
        store2 = get_vector_store("tenant_iso_same")
        assert store1 is store2
