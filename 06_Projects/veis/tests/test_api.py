import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    """Fixture for test client"""
    return TestClient(app)


def test_root_endpoint(client):
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "app" in data
    assert "version" in data
    assert "status" in data


def test_health_check(client):
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_list_observations(client):
    """Test listing observations"""
    response = client.get("/observations/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_list_zones(client):
    """Test listing zones"""
    response = client.get("/zones/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_list_incidents(client):
    """Test listing incidents"""
    response = client.get("/incidents/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
