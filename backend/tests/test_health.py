from fastapi.testclient import TestClient

from app.main import create_app


def test_health_endpoint_reports_application_and_database_state():
    client = TestClient(create_app())

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "brahmaai-studio-api",
        "database": "not_configured",
    }


def test_health_reports_connected_database_when_configured():
    app = create_app(database_url="sqlite://", create_tables=True)
    client = TestClient(app)

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["database"] == "connected"
