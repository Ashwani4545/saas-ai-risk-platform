"""Retrieval over the underwriting policy knowledge base.

Design choice worth being upfront about: this uses TF-IDF (scikit-learn,
already a project dependency) over paragraph-level chunks rather than a
dense embedding model. That's deliberate - a dense retriever needs a
model download (network access this project can't assume in every
environment it might run in) and doesn't add much value over a handful of
short policy documents like these. The interface (`retrieve(query, k)` ->
scored chunks) is the same interface a real embedding-based retriever
would expose, so swapping in sentence-transformers + a proper vector DB
(pgvector, Chroma, or the FAISS store already in this repo) behind this
same function is a contained change, not a rewrite - noted as a next step
rather than pretended to already be done.
"""
import os
import re
from dataclasses import dataclass
from typing import List

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

KB_DIR = os.path.join(os.path.dirname(__file__), "knowledge_base")


@dataclass
class Chunk:
    doc: str
    text: str


def _load_chunks() -> List[Chunk]:
    chunks = []
    for filename in sorted(os.listdir(KB_DIR)):
        if not filename.endswith(".md"):
            continue
        with open(os.path.join(KB_DIR, filename), encoding="utf-8") as f:
            content = f.read()
        # paragraph-level chunks; skip the H1 title line
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", content) if p.strip() and not p.strip().startswith("# ")]
        for p in paragraphs:
            chunks.append(Chunk(doc=filename, text=p))
    return chunks


class PolicyRetriever:
    def __init__(self):
        self.chunks = _load_chunks()
        self._vectorizer = TfidfVectorizer(stop_words="english")
        self._matrix = self._vectorizer.fit_transform([c.text for c in self.chunks]) if self.chunks else None

    def retrieve(self, query: str, k: int = 3) -> List[dict]:
        if not self.chunks or self._matrix is None:
            return []
        query_vec = self._vectorizer.transform([query])
        scores = cosine_similarity(query_vec, self._matrix)[0]
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        results = []
        for i in ranked[:k]:
            if scores[i] <= 0:
                continue
            results.append({"doc": self.chunks[i].doc, "text": self.chunks[i].text, "score": round(float(scores[i]), 4)})
        return results


_retriever: PolicyRetriever = None


def get_retriever() -> PolicyRetriever:
    global _retriever
    if _retriever is None:
        _retriever = PolicyRetriever()
    return _retriever
