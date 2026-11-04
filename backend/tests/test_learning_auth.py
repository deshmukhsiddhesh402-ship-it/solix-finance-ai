"""HTTP regression coverage for Learning Mode JWT and tenant authorization."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt

from app.core.auth_dependencies import get_authenticated_user
from app.core.config import settings
from app.core.db import get_db
from app.core.security import create_access_token
from app.models.auth_user import User
from app.models.enterprise import OrgMembership
from app.routers import learning

USER_ID = uuid4()
ORG_ID = uuid4()
OTHER_ORG_ID = uuid4()


class FakeQuery:
    def __init__(self, model):
        self.model = model

    def filter(self, *criteria):
        return self

    def first(self):
        if self.model is User:
            return SimpleNamespace(id=USER_ID, org_id=ORG_ID)
        if self.model is OrgMembership:
            return SimpleNamespace(user_id=USER_ID, org_id=ORG_ID, role="accountant")
        return None


class FakeDB:
    def query(self, model):
        return FakeQuery(model)


@pytest.fixture
 def client(monkeypatch):
    app = FastAPI()
    app.include_router(learning.router, prefix="/api/learning")
    app.dependency_overrides[get_db] = lambda: FakeDB()
    monkeypatch.setattr(learning, "learning_tutor_prompt", lambda *args: ("system", "question"))
    monkeypatch.setattr(learning, "quiz_generation_prompt", lambda *args: ("system", "quiz"))
    monkeypatch.setattr(learning, "ask_claude", lambda *args, **kwargs: "Tutor answer")
    return TestClient(app)


def _authorization(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _expired_token() -> str:
    return jwt.encode(
        {"sub": str(USER_ID), "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        ("/api/learning/ask", {"topic": "Excel", "question": "How do I use SUM?"}),
        ("/api/learning/generate-quiz", {"topic": "Excel", "num_questions": 2}),
    ],
)
def test_learning_ai_endpoints_require_jwt(client, path, payload):
    response = client.post(path, json=payload)
    assert response.status_code == 401
    assert "access_token" not in response.text


@pytest.mark.parametrize("token", ["not-a-jwt", _expired_token()])
@pytest.mark.parametrize(
    ("path", "payload"),
    [
        ("/api/learning/ask", {"topic": "Excel", "question": "How do I use SUM?"}),
        ("/api/learning/generate-quiz", {"topic": "Excel", "num_questions": 2}),
    ],
)
def test_learning_ai_endpoints_reject_invalid_or_expired_jwt(client, path, payload, token):
    response = client.post(path, json=payload, headers=_authorization(token))
    assert response.status_code == 401
    assert "access_token" not in response.text


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        ("/api/learning/ask", {"topic": "Excel", "question": "How do I use SUM?"}),
        ("/api/learning/generate-quiz", {"topic": "Excel", "num_questions": 2}),
    ],
)
def test_learning_ai_endpoints_allow_authorized_tenant_user(client, monkeypatch, path, payload):
    if path.endswith("/generate-quiz"):
        monkeypatch.setattr(learning, "ask_claude", lambda *args, **kwargs: "[]")
    response = client.post(path, json=payload, headers=_authorization(create_access_token(str(USER_ID))))
    assert response.status_code == 200
    assert "access_token" not in response.text


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        ("/api/learning/ask", {"topic": "Excel", "question": "How do I use SUM?"}),
        ("/api/learning/generate-quiz", {"topic": "Excel", "num_questions": 2}),
    ],
)
def test_learning_ai_endpoints_reject_cross_tenant_org_id(client, path, payload):
    response = client.post(
        f"{path}?org_id={OTHER_ORG_ID}",
        json=payload,
        headers=_authorization(create_access_token(str(USER_ID))),
    )
    assert response.status_code == 403


def test_learning_ai_endpoints_reject_insufficient_membership_permission(client, monkeypatch):
    from app.core.auth_dependencies import require_user_permission

    def auditor_permission(*args, **kwargs):
        from app.models.enterprise import OrgMembership as Membership

        class AuditorQuery(FakeQuery):
            def first(self):
                if self.model is User:
                    return SimpleNamespace(id=USER_ID, org_id=ORG_ID)
                if self.model is Membership:
                    return SimpleNamespace(user_id=USER_ID, org_id=ORG_ID, role="auditor")
                return None

        return AuditorQuery

    # Replace the dependency implementation's membership lookup result without
    # bypassing JWT parsing or the production permission matrix.
    monkeypatch.setattr("app.core.auth_dependencies.has_permission", lambda role, resource, action: False)
    token = create_access_token(str(USER_ID))
    for path, payload in [
        ("/api/learning/ask", {"topic": "Excel", "question": "How do I use SUM?"}),
        ("/api/learning/generate-quiz", {"topic": "Excel", "num_questions": 2}),
    ]:
        response = client.post(path, json=payload, headers=_authorization(token))
        assert response.status_code == 403


def test_learning_topics_remain_public(client):
    response = client.get("/api/learning/topics")
    assert response.status_code == 200
    assert "Excel" in response.json()["topics"]
