"""FAISS vector store with persistence and per-tenant customer embeddings.

Each tenant gets its own on-disk index under data/faiss_index/{tenant_id}/,
and get_vector_store() is keyed by tenant_id - so a similarity search for
one tenant can only ever return that tenant's own customers. Previously
there was a single global index shared by everyone, which meant the
"similar customers" endpoint could return another company's customers.
"""
import faiss
import numpy as np
import os
import pickle
import threading
from typing import List, Optional, Dict, Any

INDEX_ROOT = "data/faiss_index"


class VectorStore:
    """Vector store for one tenant's customer risk embeddings."""

    def __init__(self, tenant_id: str, dimension: int = 8):
        self.tenant_id = tenant_id
        self.dimension = dimension
        self.index = faiss.IndexFlatL2(dimension)
        self.id_map: Dict[int, int] = {}
        self.reverse_map: Dict[int, int] = {}
        self._load_if_exists()

    def _paths(self):
        base = f"{INDEX_ROOT}/{self.tenant_id}"
        return f"{base}/index.faiss", f"{base}/id_map.pkl"

    def _load_if_exists(self):
        index_file, map_file = self._paths()
        if os.path.exists(index_file) and os.path.exists(map_file):
            self.index = faiss.read_index(index_file)
            with open(map_file, "rb") as f:
                data = pickle.load(f)
                self.id_map = data["id_map"]
                self.reverse_map = data["reverse_map"]

    def save(self):
        index_file, map_file = self._paths()
        os.makedirs(os.path.dirname(index_file), exist_ok=True)
        faiss.write_index(self.index, index_file)
        with open(map_file, "wb") as f:
            pickle.dump({"id_map": self.id_map, "reverse_map": self.reverse_map}, f)

    def add_customer_embedding(self, customer_id: int, embedding: np.ndarray) -> int:
        vec = np.array([embedding]).astype("float32")
        idx = self.index.ntotal
        self.index.add(vec)
        self.id_map[customer_id] = idx
        self.reverse_map[idx] = customer_id
        return idx

    def search_similar_customers(
        self, query_embedding: np.ndarray, k: int = 5, exclude_customer_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        if self.index.ntotal == 0:
            return []

        q = np.array([query_embedding]).astype("float32")
        search_k = k + 1 if exclude_customer_id else k
        distances, indices = self.index.search(q, min(search_k, self.index.ntotal))

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1:
                break
            customer_id = self.reverse_map.get(int(idx))
            if customer_id is None:
                continue
            if exclude_customer_id and customer_id == exclude_customer_id:
                continue
            results.append(
                {
                    "customer_id": customer_id,
                    "distance": float(dist),
                    "similarity_score": 1.0 / (1.0 + float(dist)),
                }
            )
            if len(results) >= k:
                break
        return results

    def get_customer_embedding(self, customer_id: int) -> Optional[np.ndarray]:
        if customer_id not in self.id_map:
            return None
        return self.index.reconstruct(self.id_map[customer_id])

    @property
    def total_embeddings(self) -> int:
        return self.index.ntotal


_stores: Dict[str, VectorStore] = {}
_lock = threading.Lock()


def get_vector_store(tenant_id: str) -> VectorStore:
    """Get (or create) the vector store for a specific tenant. tenant_id is
    required - there is no default/shared store, by design."""
    with _lock:
        if tenant_id not in _stores:
            _stores[tenant_id] = VectorStore(tenant_id=tenant_id)
        return _stores[tenant_id]
