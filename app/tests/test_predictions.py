"""Тесты ML-запросов, списания кредитов и истории предсказаний."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from worker.main import process_task


def test_create_prediction_success(client: TestClient, auth_headers, flask_app):
    headers = auth_headers("ml_user", "pass1234", 100.0)
    me = client.get("/api/users/me", headers=headers).json()
    user_id = me["id"]

    response = client.post(
        "/api/predictions/",
        headers=headers,
        json={"model_id": 1, "image_path": "uploads/test_photo.jpg"},
    )
    assert response.status_code == 201
    data = response.json()
    assert len(data["accepted"]) == 1
    assert data["balance"] == 100.0
    assert data["price_per_item"] == 10.0
    task_id = data["accepted"][0]["id"]

    with flask_app.app_context():
        with patch("worker.predictor.time.sleep"):
            process_task(task_id)

    detail = client.get(f"/api/predictions/{task_id}", headers=headers).json()
    assert detail["status"] == "completed"
    assert detail["predictions_count"] > 0
    assert detail["charged"] == 10.0

    balance = client.get(f"/api/balance/{user_id}", headers=headers).json()
    assert balance["balance"] == 90.0


def test_insufficient_balance_for_prediction(client: TestClient, auth_headers):
    headers = auth_headers("poor_user", "pass1234", 5.0)
    response = client.post(
        "/api/predictions/",
        headers=headers,
        json={"model_id": 1, "image_path": "uploads/photo.jpg"},
    )
    assert response.status_code == 400
    assert "Недостаточно средств" in response.json()["detail"]


def test_invalid_input_rejected(client: TestClient, auth_headers):
    headers = auth_headers("invalid_user", "pass1234", 100.0)
    response = client.post(
        "/api/predictions/",
        headers=headers,
        json={"model_id": 1, "items": ["", "pending", "uploads/ok.jpg"]},
    )
    assert response.status_code == 201
    data = response.json()
    assert len(data["accepted"]) == 1
    assert len(data["rejected"]) == 2
    assert data["accepted"][0]["image_path"] == "uploads/ok.jpg"


def test_all_invalid_input(client: TestClient, auth_headers):
    headers = auth_headers("all_bad", "pass1234", 100.0)
    response = client.post(
        "/api/predictions/",
        headers=headers,
        json={"model_id": 1, "items": ["", "null"]},
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "отклонены" in detail["message"]


def test_no_charge_on_ml_failure(client: TestClient, auth_headers, flask_app):
    headers = auth_headers("fail_user", "pass1234", 100.0)
    me = client.get("/api/users/me", headers=headers).json()
    user_id = me["id"]

    response = client.post(
        "/api/predictions/",
        headers=headers,
        json={"model_id": 1, "image_path": "uploads/fail.jpg"},
    )
    task_id = response.json()["accepted"][0]["id"]

    with flask_app.app_context():
        with patch("worker.predictor.run_prediction", side_effect=RuntimeError("ML error")):
            with pytest.raises(RuntimeError):
                process_task(task_id)

    detail = client.get(f"/api/predictions/{task_id}", headers=headers).json()
    assert detail["status"] == "failed"
    assert detail["charged"] == 0.0

    balance = client.get(f"/api/balance/{user_id}", headers=headers).json()
    assert balance["balance"] == 100.0


def test_prediction_history(client: TestClient, auth_headers, flask_app):
    headers = auth_headers("hist_ml", "pass1234", 100.0)
    me = client.get("/api/users/me", headers=headers).json()
    user_id = me["id"]

    created = client.post(
        "/api/predictions/",
        headers=headers,
        json={"model_id": 1, "image_path": "uploads/hist.jpg"},
    ).json()
    task_id = created["accepted"][0]["id"]

    with flask_app.app_context():
        with patch("worker.predictor.time.sleep"):
            process_task(task_id)

    history = client.get(
        f"/api/predictions/history/{user_id}",
        headers=headers,
    ).json()
    assert history["user_id"] == user_id
    assert len(history["predictions"]) == 1
    assert history["predictions"][0]["id"] == task_id
    assert history["predictions"][0]["status"] == "completed"
    assert history["predictions"][0]["charged"] == 10.0


def test_purchase_transaction_in_history(client: TestClient, auth_headers, flask_app):
    headers = auth_headers("tx_ml", "pass1234", 100.0)
    me = client.get("/api/users/me", headers=headers).json()
    user_id = me["id"]

    task_id = client.post(
        "/api/predictions/",
        headers=headers,
        json={"model_id": 1, "image_path": "uploads/tx.jpg"},
    ).json()["accepted"][0]["id"]

    with flask_app.app_context():
        with patch("worker.predictor.time.sleep"):
            process_task(task_id)

    txs = client.get(
        f"/api/balance/transactions/{user_id}",
        headers=headers,
    ).json()["transactions"]
    purchase = [tx for tx in txs if tx["type"] == "purchase"]
    assert len(purchase) == 1
    assert purchase[0]["amount"] == 10.0
    assert purchase[0]["task_id"] == task_id
