def test_register_login_and_authenticated_session(client):
    registered = client.post(
        "/api/v1/auth/register",
        json={"email": "Aman@example.com", "password": "correct horse battery", "display_name": "Aman"},
    )
    assert registered.status_code == 201
    assert registered.json()["email"] == "aman@example.com"
    assert "password" not in registered.json()

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "aman@example.com", "password": "correct horse battery"},
    )
    assert login.status_code == 200
    assert login.json()["csrf_token"]
    assert "bas_session" in client.cookies

    current = client.get("/api/v1/auth/me")
    assert current.status_code == 200
    assert current.json()["email"] == "aman@example.com"


def test_duplicate_registration_is_rejected(client):
    payload = {"email": "same@example.com", "password": "correct horse battery"}
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    duplicate = client.post("/api/v1/auth/register", json=payload)
    assert duplicate.status_code == 409


def test_invalid_credentials_and_missing_session_are_rejected(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "wrong password"},
    )
    assert response.status_code == 401
    assert client.get("/api/v1/auth/me").status_code == 401


def test_logout_requires_csrf_token_and_revokes_session(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "logout@example.com", "password": "correct horse battery"},
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "logout@example.com", "password": "correct horse battery"},
    )
    csrf = login.json()["csrf_token"]

    denied = client.post("/api/v1/auth/logout")
    assert denied.status_code == 403

    logged_out = client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf})
    assert logged_out.status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401


def test_secure_cookie_flag_is_enabled_for_production_configuration():
    from fastapi.testclient import TestClient
    from app.main import create_app

    app = create_app(database_url="sqlite://", create_tables=True, secure_cookies=True)
    with TestClient(app) as secure_client:
        secure_client.post(
            "/api/v1/auth/register",
            json={"email": "secure@example.com", "password": "correct horse battery"},
        )
        response = secure_client.post(
            "/api/v1/auth/login",
            json={"email": "secure@example.com", "password": "correct horse battery"},
        )
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "secure" in cookie
    assert "samesite=lax" in cookie
