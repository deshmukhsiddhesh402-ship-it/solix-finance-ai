"""Regression tests ensuring audit diffs do not retain authentication secrets."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.audit_engine import build_audit_entry, diff_fields


def test_changed_sensitive_fields_are_redacted():
    changes = diff_fields(
        {
            "access_token": "old-token",
            "api_key": "old-api-key",
            "password": "old-password",
            "display_name": "Old name",
        },
        {
            "access_token": "new-token",
            "api_key": "new-api-key",
            "password": "new-password",
            "display_name": "New name",
        },
    )

    assert changes["access_token"] == {"before": "[REDACTED]", "after": "[REDACTED]"}
    assert changes["api_key"] == {"before": "[REDACTED]", "after": "[REDACTED]"}
    assert changes["password"] == {"before": "[REDACTED]", "after": "[REDACTED]"}
    assert changes["display_name"] == {"before": "Old name", "after": "New name"}


def test_sensitive_fields_are_redacted_on_create_and_delete():
    created = diff_fields(None, {"otp": "123456", "name": "Siddhesh"})
    deleted = diff_fields({"refresh-token": "refresh-secret"}, None)

    assert created["otp"] == {"before": None, "after": "[REDACTED]"}
    assert created["name"] == {"before": None, "after": "Siddhesh"}
    assert deleted["refresh-token"] == {"before": "[REDACTED]", "after": None}


def test_unchanged_sensitive_fields_are_not_added_to_diff():
    assert diff_fields({"secret": "same"}, {"secret": "same"}) == {}


def test_nested_sensitive_fields_are_redacted_recursively():
    changes = diff_fields(
        {"metadata": {"api_key": "old-key", "profile": [{"clientSecret": "old-secret"}]}},
        {"metadata": {"api_key": "new-key", "profile": [{"clientSecret": "new-secret"}]}},
    )

    before = changes["metadata"]["before"]
    after = changes["metadata"]["after"]
    assert before["api_key"] == "[REDACTED]"
    assert after["api_key"] == "[REDACTED]"
    assert before["profile"][0]["clientSecret"] == "[REDACTED]"
    assert after["profile"][0]["clientSecret"] == "[REDACTED]"


def test_private_keys_cookies_and_bearer_values_are_redacted():
    changes = diff_fields(
        None,
        {
            "private_key": "private-material",
            "privateKey": "camel-private-material",
            "cookie": "session=secret",
            "bearer": "bearer-secret",
        },
    )
    for field in ("private_key", "privateKey", "cookie", "bearer"):
        assert changes[field]["after"] == "[REDACTED]"


def test_sensitive_fields_inside_tuples_are_redacted_recursively():
    changes = diff_fields(
        None,
        {"metadata": ({"session_token": "secret-session"}, {"private_key": "private-material", "privateKey": "camel-private-material"})},
    )
    nested = changes["metadata"]["after"]
    assert isinstance(nested, tuple)
    assert nested[0]["session_token"] == "[REDACTED]"
    assert nested[1]["private_key"] == "[REDACTED]"
    assert nested[1]["privateKey"] == "[REDACTED]"



def test_sensitive_fields_inside_sets_of_pairs_are_redacted_recursively():
    changes = diff_fields(
        None,
        {"metadata": {("session_token", "secret-session"), ("display_name", "Visible")}},
    )
    nested = changes["metadata"]["after"]
    assert nested == {("session_token", "[REDACTED]"), ("display_name", "Visible")}



def test_sensitive_fields_inside_frozensets_of_pairs_are_redacted_recursively():
    changes = diff_fields(
        None,
        {"metadata": frozenset({("refresh_token", "secret-refresh"), ("label", "Visible")})},
    )
    nested = changes["metadata"]["after"]
    assert isinstance(nested, frozenset)
    assert nested == frozenset({("refresh_token", "[REDACTED]"), ("label", "Visible")})


def test_sensitive_field_names_with_spaces_and_punctuation_are_redacted():
    changes = diff_fields(
        None,
        {
            "API Key": "api-secret",
            "private key": "private-secret",
            "client.api-key": "client-secret",
            "display name": "Visible",
        },
    )

    assert changes["API Key"]["after"] == "[REDACTED]"
    assert changes["private key"]["after"] == "[REDACTED]"
    assert changes["client.api-key"]["after"] == "[REDACTED]"
    assert changes["display name"]["after"] == "Visible"


def test_sensitive_key_value_pairs_inside_tuples_and_lists_are_redacted():
    changes = diff_fields(
        None,
        {
            "metadata": (
                ("password", "tuple-secret"),
                [("api key", "list-secret"), ("label", "Visible")],
            )
        },
    )

    nested = changes["metadata"]["after"]
    assert nested[0] == ("password", "[REDACTED]")
    assert nested[1] == [("api key", "[REDACTED]"), ("label", "Visible")]


def test_diff_distinguishes_added_null_and_removed_null_fields():
    added = diff_fields({}, {"optional_note": None})
    removed = diff_fields({"optional_note": None}, {})

    assert added == {"optional_note": {"before": {"$solix_audit_missing": True}, "after": None}}
    assert removed == {"optional_note": {"before": None, "after": {"$solix_audit_missing": True}}}


def test_diff_still_omits_unchanged_explicit_null_fields():
    assert diff_fields({"optional_note": None}, {"optional_note": None}) == {}


def test_diff_rejects_non_dictionary_snapshots():
    import pytest

    with pytest.raises(ValueError, match="before snapshot"):
        diff_fields([], {"name": "value"})
    with pytest.raises(ValueError, match="after snapshot"):
        diff_fields({"name": "value"}, "not-a-dictionary")


def test_audit_entry_rejects_empty_organization_identifier():
    import pytest

    with pytest.raises(ValueError, match="organization id"):
        build_audit_entry(
            user_id="user-1",
            org_id="",
            action="create",
            entity_type="invoice",
            entity_id="invoice-1",
        )



def test_persisted_audit_changes_are_redacted_again_at_read_boundary():
    from app.services.audit_engine import redact_audit_changes

    legacy = {
        "api_key": {"before": "old-plaintext-key", "after": "new-plaintext-key"},
        "metadata": {
            "before": {"refresh-token": "old-refresh-secret", "label": "Visible"},
            "after": {"refresh-token": "new-refresh-secret", "label": "Updated"},
        },
    }

    sanitized = redact_audit_changes(legacy)

    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["metadata"]["before"]["refresh-token"] == "[REDACTED]"
    assert sanitized["metadata"]["after"]["refresh-token"] == "[REDACTED]"
    assert sanitized["metadata"]["before"]["label"] == "Visible"
    assert sanitized["metadata"]["after"]["label"] == "Updated"
    # The read guard must not mutate the ORM/JSON value stored in the database.
    assert legacy["api_key"]["before"] == "old-plaintext-key"


def test_persisted_audit_changes_reject_malformed_non_object_values():
    from app.services.audit_engine import redact_audit_changes

    assert redact_audit_changes(None) is None
    assert redact_audit_changes(["unstructured", "legacy"]) is None


def test_audit_log_endpoint_redacts_legacy_rows_before_returning_them():
    from datetime import datetime, timezone
    from types import SimpleNamespace
    from uuid import uuid4

    from app.models.enterprise import AuditLog
    from app.routers.enterprise import view_audit_log

    org_id = uuid4()
    row = SimpleNamespace(
        id=uuid4(),
        user_id=uuid4(),
        action="edit",
        entity_type="integration",
        entity_id="integration-1",
        changes={
            "api_key": {"before": "legacy-key", "after": "another-key"},
            "settings": {
                "before": {"display_name": "Old", "clientSecret": "legacy-secret"},
                "after": {"display_name": "New", "clientSecret": "new-secret"},
            },
        },
        created_at=datetime(2026, 11, 8, tzinfo=timezone.utc),
    )

    class FakeQuery:
        def filter(self, *criteria):
            self.criteria = criteria
            return self

        def order_by(self, *criteria):
            return self

        def limit(self, value):
            return self

        def all(self):
            return [row]

    class FakeDB:
        def query(self, model):
            assert model is AuditLog
            return FakeQuery()

    response = view_audit_log(org_id=str(org_id), db=FakeDB(), _user=str(uuid4()))

    changes = response["entries"][0]["changes"]
    assert changes["api_key"] == "[REDACTED]"
    assert changes["settings"]["before"]["clientSecret"] == "[REDACTED]"
    assert changes["settings"]["after"]["clientSecret"] == "[REDACTED]"
    assert changes["settings"]["before"]["display_name"] == "Old"
    assert row.changes["api_key"]["before"] == "legacy-key"
