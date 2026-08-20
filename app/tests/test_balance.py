from fastapi.testclient import TestClient


def test_get_initial_balance(client: TestClient, auth_headers):
    headers = auth_headers("wallet_user", "pass1234", 100.0)
    me = client.get("/api/users/me", headers=headers).json()
    user_id = me["id"]

    response = client.get(f"/api/balance/{user_id}", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"user_id": user_id, "balance": 100.0}


def test_top_up_balance(client: TestClient, auth_headers):
    headers = auth_headers("topup_user", "pass1234", 50.0)
    me = client.get("/api/users/me", headers=headers).json()
    user_id = me["id"]

    response = client.post(
        "/api/balance/top-up",
        headers=headers,
        json={"amount": 75.0},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["balance"] == 125.0
    assert data["transaction"]["type"] == "top_up"
    assert data["transaction"]["amount"] == 75.0

    balance = client.get(f"/api/balance/{user_id}", headers=headers).json()
    assert balance["balance"] == 125.0


def test_transaction_history(client: TestClient, auth_headers):
    headers = auth_headers("history_user", "pass1234", 10.0)
    me = client.get("/api/users/me", headers=headers).json()
    user_id = me["id"]

    client.post("/api/balance/top-up", headers=headers, json={"amount": 30.0})
    client.post("/api/balance/top-up", headers=headers, json={"amount": 20.0})

    response = client.get(
        f"/api/balance/transactions/{user_id}",
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == user_id
    assert len(data["transactions"]) == 2
    types = {tx["type"] for tx in data["transactions"]}
    assert types == {"top_up"}
    amounts = sorted(tx["amount"] for tx in data["transactions"])
    assert amounts == [20.0, 30.0]
