from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def signed_in(settings=None):
    client = TestClient(create_app(database_url="sqlite://", create_tables=True, settings=settings))
    client.post("/api/v1/auth/register", json={"email": "status@example.com", "password": "StrongPass123!"})
    client.post("/api/v1/auth/login", json={"email": "status@example.com", "password": "StrongPass123!"})
    return client


def test_assistant_status_requires_authentication():
    client = TestClient(create_app(database_url="sqlite://", create_tables=True))
    assert client.get("/api/v1/assistant/status").status_code == 401


def test_assistant_status_never_discloses_model_endpoint():
    settings = Settings(_env_file=None, local_llm_enabled=True, local_llm_model="qwen2.5:7b", local_llm_base_url="http://127.0.0.1:11434")
    client = signed_in(settings)
    response = client.get("/api/v1/assistant/status")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"enabled", "configured", "reachable", "model_available", "code"}
    assert "127.0.0.1" not in response.text
