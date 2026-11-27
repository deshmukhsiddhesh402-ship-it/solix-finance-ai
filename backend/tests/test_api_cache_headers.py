from fastapi.testclient import TestClient

from app.main import app


def test_api_responses_are_not_cacheable():
    response = TestClient(app).get("/api/health")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
