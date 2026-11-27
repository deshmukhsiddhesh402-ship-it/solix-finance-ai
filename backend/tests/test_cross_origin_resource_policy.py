from fastapi.testclient import TestClient

from app.main import app


def test_api_responses_restrict_cross_origin_resource_loading():
    response = TestClient(app).get("/api/health")

    assert response.status_code == 200
    assert response.headers["cross-origin-resource-policy"] == "same-origin"
