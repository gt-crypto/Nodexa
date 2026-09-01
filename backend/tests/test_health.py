"""Tests for the health check endpoint."""
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_health_check():
    """Verify GET /health returns 200 OK and expected structure."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "nodal-sentinel-backend"
    assert data["version"] == "0.1.0"
    assert "timestamp" in data
