"""Tests for the retrieval-augmented explanation feature.

These run without ANTHROPIC_API_KEY set (as CI does) and exercise the
template-fallback path, which is real code, not a mock - it's what every
user of this project sees unless they configure their own key.
"""
from fastapi.testclient import TestClient

from api.main import app
from rag.retriever import get_retriever

client = TestClient(app)
AUTH = {"X-API-Key": "demo-api-key-tenant1"}


class TestRetriever:
    def test_loads_knowledge_base(self):
        retriever = get_retriever()
        assert len(retriever.chunks) > 0

    def test_dispute_query_matches_dispute_policy(self):
        results = get_retriever().retrieve("customer has multiple recent disputes", k=3)
        docs = [r["doc"] for r in results]
        assert "dispute_policy.md" in docs

    def test_account_age_query_matches_account_policy(self):
        results = get_retriever().retrieve("brand new account no transaction history", k=3)
        docs = [r["doc"] for r in results]
        assert "account_history_policy.md" in docs

    def test_irrelevant_query_returns_low_or_no_results(self):
        results = get_retriever().retrieve("zzz qqq nonsense unrelated words", k=3)
        # TF-IDF on a tiny corpus can still return weakly-scored matches;
        # what matters is it doesn't crash and scores are low.
        for r in results:
            assert r["score"] < 0.3


class TestExplainEndpoint:
    def test_explain_requires_auth(self):
        response = client.post("/explain", json={"customer_id": 1})
        assert response.status_code == 401

    def test_explain_returns_grounded_explanation(self):
        response = client.post("/explain", json={"customer_id": 1}, headers=AUTH)
        assert response.status_code == 200
        data = response.json()
        assert "explanation" in data
        assert data["generated_by"] in ("llm", "template_fallback")
        assert isinstance(data["sources"], list)

    def test_explain_without_llm_key_uses_fallback(self):
        """CI never sets ANTHROPIC_API_KEY, so this should always take the
        template path - confirms the feature doesn't silently no-op."""
        response = client.post("/explain", json={"customer_id": 2}, headers=AUTH)
        data = response.json()
        assert data["generated_by"] == "template_fallback"
        assert len(data["explanation"]) > 0


class TestPolicyQAEndpoint:
    def test_policy_question_requires_auth(self):
        response = client.post("/policy/ask", json={"question": "what about disputes?"})
        assert response.status_code == 401

    def test_policy_question_returns_sources(self):
        response = client.post(
            "/policy/ask", json={"question": "what happens with multiple disputes?"}, headers=AUTH
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["sources"]) > 0
        assert "answer" in data
