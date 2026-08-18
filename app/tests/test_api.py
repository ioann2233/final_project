"""Тесты health-check и корневого эндпоинта."""

from fastapi.testclient import TestClient


def test_health(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_root(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["message"] == "ML Service API"


def test_list_models(client: TestClient):
    response = client.get("/api/models/")
    assert response.status_code == 200
    models = response.json()
    assert len(models) >= 1
    assert models[0]["name"] == "Test YOLO"
    assert models[0]["price"] == 10.0
