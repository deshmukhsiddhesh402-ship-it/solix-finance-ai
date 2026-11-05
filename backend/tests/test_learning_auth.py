from uuid import uuid4

import pytest
from fastapi import HTTPException

import app.routers.enterprise as enterprise
import app.routers.learning as learning
from app.models.auth_user import User
from app.models.enterprise import OrgMembership
from app.services.rbac_engine import has_permission


@pytest.mark.parametrize("role", ["admin", "accountant", "auditor"])
def test_learning_create_permission_is_available_to_all_tenant_roles(role):
    assert has_permission(role, "learning", "create")


def test_learning_ai_routes_require_the_backend_permission_dependency():
    guarded_paths = {"/ask", "/generate-quiz"}
    routes = {route.path: route for route in learning.router.routes}

    for path in guarded_paths:
        assert any(
            dependency.call is learning._require_learning_access
            for dependency in routes[path].dependant.dependencies
        )


def test_learning_access_rejects_missing_bearer_token_before_database_lookup():
    class UnexpectedDB:
        def query(self, model):
            raise AssertionError("Database must not be queried without a bearer token.")

    with pytest.raises(HTTPException) as exc:
        learning._require_learning_access(
            org_id=str(uuid4()),
            authorization="",
            db=UnexpectedDB(),
        )

    assert exc.value.status_code == 401


def test_learning_access_rejects_invalid_backend_jwt(monkeypatch):
    monkeypatch.setattr(enterprise, "decode_access_token", lambda token: None)

    class UnexpectedDB:
        def query(self, model):
            raise AssertionError("Database must not be queried for an invalid token.")

    with pytest.raises(HTTPException) as exc:
        learning._require_learning_access(
            org_id=str(uuid4()),
            authorization="Bearer invalid-token",
            db=UnexpectedDB(),
        )

    assert exc.value.status_code == 401


def test_learning_access_requires_membership_in_the_requested_tenant(monkeypatch):
    user = User(id=uuid4(), org_id=uuid4(), email="learner@example.com", role="accountant")

    class FakeQuery:
        def __init__(self, model):
            self.model = model

        def filter(self, *conditions):
            return self

        def first(self):
            return user if self.model is User else None

    class FakeDB:
        def query(self, model):
            return FakeQuery(model)

    monkeypatch.setattr(enterprise, "decode_access_token", lambda token: {"sub": str(user.id)})

    with pytest.raises(HTTPException) as exc:
        learning._require_learning_access(
            org_id=str(uuid4()),
            authorization="Bearer valid-token",
            db=FakeDB(),
        )

    assert exc.value.status_code == 403


@pytest.mark.parametrize("role", ["admin", "accountant", "auditor"])
def test_learning_access_accepts_authenticated_tenant_member(monkeypatch, role):
    user = User(id=uuid4(), org_id=uuid4(), email="learner@example.com", role="accountant")
    membership = OrgMembership(user_id=user.id, org_id=user.org_id, role=role)

    class FakeQuery:
        def __init__(self, model):
            self.model = model

        def filter(self, *conditions):
            return self

        def first(self):
            return user if self.model is User else membership

    class FakeDB:
        def query(self, model):
            return FakeQuery(model)

    monkeypatch.setattr(enterprise, "decode_access_token", lambda token: {"sub": str(user.id)})

    result = learning._require_learning_access(
        org_id=str(user.org_id),
        authorization="Bearer valid-token",
        db=FakeDB(),
    )

    assert result == str(user.id)


def test_learning_access_rejects_unknown_membership_role(monkeypatch):
    user = User(id=uuid4(), org_id=uuid4(), email="learner@example.com", role="accountant")
    membership = OrgMembership(user_id=user.id, org_id=user.org_id, role="owner")

    class FakeQuery:
        def __init__(self, model):
            self.model = model

        def filter(self, *conditions):
            return self

        def first(self):
            return user if self.model is User else membership

    class FakeDB:
        def query(self, model):
            return FakeQuery(model)

    monkeypatch.setattr(enterprise, "decode_access_token", lambda token: {"sub": str(user.id)})

    with pytest.raises(HTTPException) as exc:
        learning._require_learning_access(
            org_id=str(user.org_id),
            authorization="Bearer valid-token",
            db=FakeDB(),
        )

    assert exc.value.status_code == 403


def test_generate_quiz_returns_only_validated_questions(monkeypatch):
    response = [{
        "question": "What is GST?",
        "options": ["A tax", "A bank", "A loan", "A salary"],
        "correct_index": 0,
        "explanation": "GST is an indirect tax.",
    }]
    monkeypatch.setattr(learning, "ask_claude", lambda *args, **kwargs: __import__("json").dumps(response))

    result = learning.generate_quiz(learning.QuizRequest(topic="GST", num_questions=1))

    assert result["questions"] == response


@pytest.mark.parametrize("response", [
    "not-json",
    '[{"question":"Q","options":["A","B"],"correct_index":0,"explanation":"Why"}]',
    '[{"question":"Q","options":["A","B","C","D"],"correct_index":4,"explanation":"Why"}]',
    '[{"question":"Q","options":["A","B","C","D"],"correct_index":0,"explanation":"Why","extra":"unexpected"}]',
    '[]',
])
def test_generate_quiz_rejects_invalid_provider_output(monkeypatch, response):
    monkeypatch.setattr(learning, "ask_claude", lambda *args, **kwargs: response)

    with pytest.raises(HTTPException) as exc:
        learning.generate_quiz(learning.QuizRequest(topic="GST", num_questions=1))

    assert exc.value.status_code == 502
