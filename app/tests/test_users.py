from fastapi.testclient import TestClient


def test_signup(client: TestClient):
    response = client.post(
        "/api/users/signup",
        json={
            "username": "alice",
            "password": "alice1234",
            "initial_balance": 50.0,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "alice"
    assert data["balance"] == 50.0
    assert data["role"] == "user"
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_signin(client: TestClient):
    client.post(
        "/api/users/signup",
        json={"username": "bob", "password": "bob1234", "initial_balance": 0},
    )
    response = client.post(
        "/api/users/signin",
        json={"username": "bob", "password": "bob1234"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "bob"
    assert "access_token" in data


def test_repeated_signin(client: TestClient):
    client.post(
        "/api/users/signup",
        json={"username": "carol", "password": "carol1234"},
    )
    first = client.post(
        "/api/users/signin",
        json={"username": "carol", "password": "carol1234"},
    )
    second = client.post(
        "/api/users/signin",
        json={"username": "carol", "password": "carol1234"},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["access_token"] != second.json()["access_token"]


def test_signin_wrong_password(client: TestClient):
    client.post(
        "/api/users/signup",
        json={"username": "dave", "password": "dave1234"},
    )
    response = client.post(
        "/api/users/signin",
        json={"username": "dave", "password": "wrong"},
    )
    assert response.status_code == 401
    assert "Неверный логин или пароль" in response.json()["detail"]


def test_signup_duplicate(client: TestClient):
    payload = {"username": "eve", "password": "eve1234"}
    client.post("/api/users/signup", json=payload)
    response = client.post("/api/users/signup", json=payload)
    assert response.status_code == 400
    assert "уже существует" in response.json()["detail"]


def test_me_endpoint(client: TestClient, auth_headers):
    headers = auth_headers("frank", "frank1234", 25.0)
    response = client.get("/api/users/me", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "frank"
    assert data["balance"] == 25.0


def test_unauthorized_without_token(client: TestClient):
    response = client.get("/api/users/me")
    assert response.status_code == 401
