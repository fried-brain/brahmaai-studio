import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture()
def client():
    app = create_app(database_url="sqlite://", create_tables=True)
    with TestClient(app) as test_client:
        yield test_client
