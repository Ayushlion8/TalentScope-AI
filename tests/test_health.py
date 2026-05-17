"""Tests for /health endpoint."""
from fastapi.testclient import TestClient


def test_health_returns_200(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200


def test_health_returns_ok(client: TestClient):
    resp = client.get("/health")
    data = resp.json()
    assert data == {"status": "ok"}


def test_app_exposes_only_required_routes(client: TestClient):
    paths = {route.path for route in client.app.routes}
    assert paths == {"/health", "/chat"}
