from fastapi.testclient import TestClient

from app.main import create_app


def test_generation_endpoint_requires_authentication_and_csrf():
    client = TestClient(create_app(database_url="sqlite://", create_tables=True))
    assert client.post("/api/v1/projects/not-a-project/assistant/layout-generation", json={
        "message": "Create a home", "floor_number": 0,
    }).status_code == 401


def test_generation_endpoint_rejects_blank_message():
    client = TestClient(create_app(database_url="sqlite://", create_tables=True))
    client.post("/api/v1/auth/register", json={"email": "blankplanner@example.com", "password": "StrongPass123!"})
    login = client.post("/api/v1/auth/login", json={"email": "blankplanner@example.com", "password": "StrongPass123!"})
    headers = {"X-CSRF-Token": login.json()["csrf_token"]}
    project = client.post("/api/v1/projects", headers=headers, json={"name": "Blank"}).json()
    response = client.post(f"/api/v1/projects/{project['id']}/assistant/layout-generation", headers=headers, json={
        "message": "   ", "floor_number": 0,
    })
    assert response.status_code == 422
