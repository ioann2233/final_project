"""Фикстуры pytest: in-memory SQLite, сид ML-модели, mock RabbitMQ."""

from __future__ import annotations

import os
from typing import Callable, Generator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-key"

from api import app as fastapi_app  # noqa: E402
from extensions import db  # noqa: E402
from main import create_app  # noqa: E402
from service.testing.ml_model import create_ml_model  # noqa: E402
from ui.context import get_flask_app  # noqa: E402


def _build_test_flask_app():
    application = create_app()
    application.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    application.config["TESTING"] = True
    return application


@pytest.fixture(name="flask_app")
def flask_app_fixture():
    get_flask_app.cache_clear()
    application = _build_test_flask_app()
    with application.app_context():
        import models  # noqa: F401

        db.drop_all()
        db.create_all()
        create_ml_model(
            name="Test YOLO",
            description="Тестовая модель",
            price=10.0,
            model_path="yolov8n.pt",
        )
    yield application
    get_flask_app.cache_clear()


@pytest.fixture(name="client")
def client_fixture(flask_app) -> Generator[TestClient, None, None]:
    patches = [
        patch("ui.context.get_flask_app", return_value=flask_app),
        patch("service.testing.ml_task.send_ml_task"),
        patch("deps.get_flask_app", return_value=flask_app),
    ]
    for item in patches:
        item.start()
    try:
        with TestClient(fastapi_app) as test_client:
            yield test_client
    finally:
        for item in patches:
            item.stop()
        get_flask_app.cache_clear()


@pytest.fixture
def auth_headers(client: TestClient) -> Callable[[str, str, float], dict]:
    """Регистрирует пользователя и возвращает заголовки Authorization."""

    def _register(
        username: str = "testuser",
        password: str = "pass1234",
        initial_balance: float = 100.0,
    ) -> dict:
        response = client.post(
            "/api/users/signup",
            json={
                "username": username,
                "password": password,
                "initial_balance": initial_balance,
            },
        )
        assert response.status_code == 201, response.text
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _register
