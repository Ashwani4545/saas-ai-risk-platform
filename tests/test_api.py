"""Tests for the API endpoints"""
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)

TENANT_1_KEY = "demo-api-key-tenant1"
TENANT_2_KEY = "demo-api-key-tenant2"


def auth_headers(api_key=TENANT_1_KEY):
    return {"X-API-Key": api_key}


class TestHealthEndpoint:
    def test_health_check(self):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestAuthIsRequired:
    """The old repo let X-Tenant-ID header alone stand in as identity;
    these confirm that no longer works."""

    def test_predict_without_auth_is_rejected(self):
        response = client.post("/predict", json={"user_id": 1}, headers={"X-Tenant-ID": "whatever-i-want"})
        assert response.status_code == 401

    def test_features_without_auth_is_rejected(self):
        response = client.get("/features/1")
        assert response.status_code == 401

    def test_invalid_api_key_rejected(self):
        response = client.post("/predict", json={"user_id": 1}, headers=auth_headers("not-a-real-key"))
        assert response.status_code == 401


class TestPredictEndpoint:
    def test_predict_basic(self):
        response = client.post("/predict", json={"user_id": 1}, headers=auth_headers())
        assert response.status_code == 200
        data = response.json()
        assert data["tenant"] == "tenant_1"
        assert "model_version" in data["data"]
        assert 0 <= data["data"]["risk_score"] <= 1
        assert data["data"]["risk_class"] in (0, 1)

    def test_predict_with_features(self):
        response = client.post(
            "/predict",
            json={"user_id": 2, "features": {"recency": 5.0, "frequency": 10.0, "monetary": 500.0, "credit_score": 750.0}},
            headers=auth_headers(),
        )
        assert response.status_code == 200
        assert 0 <= response.json()["data"]["risk_score"] <= 1

    def test_predict_deterministic_ab(self):
        versions = set()
        for _ in range(3):
            response = client.post("/predict", json={"user_id": 42}, headers=auth_headers())
            versions.add(response.json()["data"]["model_version"])
        assert len(versions) == 1

    def test_predict_ab_distribution(self):
        models = set()
        for user_id in range(1, 60):
            response = client.post("/predict", json={"user_id": user_id}, headers=auth_headers())
            models.add(response.json()["data"]["model_version"])
        assert "model_A" in models
        assert "model_B" in models

    def test_tenant_cannot_read_another_tenants_predictions(self):
        client.post("/predict", json={"user_id": 777}, headers=auth_headers(TENANT_1_KEY))

        own = client.get("/predictions/recent", headers=auth_headers(TENANT_1_KEY)).json()["predictions"]
        other = client.get("/predictions/recent", headers=auth_headers(TENANT_2_KEY)).json()["predictions"]

        assert any(p["customer_id"] == 777 for p in own)
        assert not any(p["customer_id"] == 777 and p["tenant_id"] == "tenant_1" for p in other)


class TestMetricsEndpoint:
    def test_metrics_endpoint(self):
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "risk_platform" in response.text


class TestAuthEndpoints:
    def test_login_success(self):
        response = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
        assert response.status_code == 200
        assert "access_token" in response.json()

    def test_login_invalid_credentials(self):
        response = client.post("/auth/login", json={"username": "admin", "password": "wrongpassword"})
        assert response.status_code == 401

    def test_authenticated_request_with_jwt(self):
        token = client.post("/auth/login", json={"username": "admin", "password": "admin123"}).json()["access_token"]
        response = client.get("/ab/stats", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200


class TestFeaturesEndpoint:
    def test_get_customer_features(self):
        response = client.get("/features/1", headers=auth_headers())
        assert response.status_code == 200
        data = response.json()
        assert "recency" in data["features"]
        assert "frequency" in data["features"]
        assert "monetary" in data["features"]


class TestSimilarCustomersEndpoint:
    def test_find_similar_customers(self):
        for user_id in range(1, 10):
            client.post("/predict", json={"user_id": user_id}, headers=auth_headers())

        response = client.post("/similar-customers", json={"customer_id": 1, "k": 3}, headers=auth_headers())
        assert response.status_code == 200
        assert "similar_customers" in response.json()
