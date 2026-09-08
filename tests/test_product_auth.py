"""Tests for the product authenticity / fraud detection domain."""
from fastapi.testclient import TestClient

from api.main import app
from product_auth.scan_service import haversine_km, compute_scan_features
from product_auth.qr_service import generate_serial, generate_qr_svg
from core import db

client = TestClient(app)
AUTH_1 = {"X-API-Key": "demo-api-key-tenant1"}
AUTH_2 = {"X-API-Key": "demo-api-key-tenant2"}

DELHI = (28.6139, 77.2090)
MUMBAI = (19.0760, 72.8777)


class TestHaversine:
    def test_same_point_is_zero_distance(self):
        assert haversine_km(*DELHI, *DELHI) == 0

    def test_delhi_mumbai_known_distance(self):
        # real-world distance is ~1150km - loose bound, just sanity checking the formula
        d = haversine_km(*DELHI, *MUMBAI)
        assert 1000 < d < 1300


class TestQRGeneration:
    def test_serial_is_unique(self):
        serials = {generate_serial() for _ in range(50)}
        assert len(serials) == 50

    def test_qr_svg_is_valid_svg(self):
        svg = generate_qr_svg(generate_serial(), "tenant_1")
        assert svg.strip().startswith("<?xml")
        assert "<svg" in svg


class TestScanFeatures:
    def test_no_history_returns_zeroed_features(self):
        features = compute_scan_features("PRD-NONEXISTENT", "tenant_1")
        assert features["scan_count"] == 0

    def test_impossible_travel_detected(self):
        db.create_product("PRD-FEATTEST1", "tenant_1", "Test Item")
        db.record_scan("PRD-FEATTEST1", "tenant_1", *DELHI)
        db.record_scan("PRD-FEATTEST1", "tenant_1", *MUMBAI)
        features = compute_scan_features("PRD-FEATTEST1", "tenant_1")
        # two scans inserted back-to-back (seconds apart) 1000+km away from
        # each other implies an enormous, physically impossible speed
        assert features["max_travel_speed_kmh"] > 900


class TestRegisterProductEndpoint:
    def test_requires_auth(self):
        response = client.post("/products/register", json={"product_name": "Test Shoe"})
        assert response.status_code == 401

    def test_register_returns_serial_and_qr(self):
        response = client.post("/products/register", json={"product_name": "Test Shoe"}, headers=AUTH_1)
        assert response.status_code == 200
        data = response.json()
        assert data["product"]["product_name"] == "Test Shoe"
        assert data["product"]["tenant_id"] == "tenant_1"
        assert "<svg" in data["qr_svg"]


class TestScanEndpoint:
    def test_requires_auth(self):
        response = client.post("/scan", json={"serial": "PRD-X", "latitude": 1.0, "longitude": 1.0})
        assert response.status_code == 401

    def test_unregistered_serial_is_flagged_unverified(self):
        response = client.post(
            "/scan", json={"serial": "PRD-DOES-NOT-EXIST", "latitude": 1.0, "longitude": 1.0}, headers=AUTH_1
        )
        assert response.status_code == 200
        data = response.json()
        assert data["verified"] is False
        assert data["risk_class"] == 1

    def test_registered_product_scan_returns_risk_assessment(self):
        reg = client.post("/products/register", json={"product_name": "Sneaker"}, headers=AUTH_1).json()
        serial = reg["product"]["serial"]

        response = client.post(
            "/scan", json={"serial": serial, "latitude": DELHI[0], "longitude": DELHI[1]}, headers=AUTH_1
        )
        assert response.status_code == 200
        data = response.json()
        assert data["verified"] is True
        assert 0 <= data["risk_score"] <= 1
        assert "explanation" in data
        assert data["generated_by"] in ("llm", "template_fallback")

    def test_impossible_travel_flagged_high_risk(self):
        reg = client.post("/products/register", json={"product_name": "Watch"}, headers=AUTH_1).json()
        serial = reg["product"]["serial"]

        client.post("/scan", json={"serial": serial, "latitude": DELHI[0], "longitude": DELHI[1]}, headers=AUTH_1)
        response = client.post(
            "/scan", json={"serial": serial, "latitude": MUMBAI[0], "longitude": MUMBAI[1]}, headers=AUTH_1
        )
        data = response.json()
        # two scans, ~1150km apart, seconds apart in wall-clock test time -
        # should read as high risk under the impossible-travel signal
        assert data["risk_class"] == 1

    def test_cannot_scan_another_tenants_product(self):
        reg = client.post("/products/register", json={"product_name": "Bag"}, headers=AUTH_1).json()
        serial = reg["product"]["serial"]

        response = client.post(
            "/scan", json={"serial": serial, "latitude": DELHI[0], "longitude": DELHI[1]}, headers=AUTH_2
        )
        data = response.json()
        assert data["verified"] is False


class TestProductHistoryEndpoint:
    def test_requires_auth(self):
        response = client.get("/products/PRD-X/history")
        assert response.status_code == 401

    def test_history_scoped_to_owning_tenant(self):
        reg = client.post("/products/register", json={"product_name": "Cap"}, headers=AUTH_1).json()
        serial = reg["product"]["serial"]
        client.post("/scan", json={"serial": serial, "latitude": DELHI[0], "longitude": DELHI[1]}, headers=AUTH_1)

        own = client.get(f"/products/{serial}/history", headers=AUTH_1)
        other = client.get(f"/products/{serial}/history", headers=AUTH_2)

        assert own.status_code == 200
        assert len(own.json()["history"]) >= 1
        assert other.status_code == 404
