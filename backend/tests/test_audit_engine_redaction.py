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
