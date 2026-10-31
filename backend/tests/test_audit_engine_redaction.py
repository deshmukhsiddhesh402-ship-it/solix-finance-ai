"""Regression tests ensuring audit diffs do not retain authentication secrets."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.audit_engine import diff_fields


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
