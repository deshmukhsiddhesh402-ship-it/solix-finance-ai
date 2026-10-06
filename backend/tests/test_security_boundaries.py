"""Focused regression tests for enterprise and accounting boundary validation."""
import pytest
from pydantic import ValidationError

from app.routers.enterprise import (
    _parse_uuid,
    CreateApiKeyRequest,
    ScheduledReportRequest,
    AddMembershipRequest,
)


def test_invalid_uuid_is_rejected_as_http_400():
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        _parse_uuid("not-a-uuid", "organization identifier")
    assert exc.value.status_code == 400


def test_api_key_name_is_bounded():
    with pytest.raises(ValidationError):
        CreateApiKeyRequest(org_id="6f1b7d5d-2c0a-4b9f-9a6d-7a0b5d9b1c22", name="")
    with pytest.raises(ValidationError):
        CreateApiKeyRequest(org_id="6f1b7d5d-2c0a-4b9f-9a6d-7a0b5d9b1c22", name="x" * 101)


def test_scheduled_report_frequency_is_allowlisted_and_bounded():
    base = {
        "org_id": "6f1b7d5d-2c0a-4b9f-9a6d-7a0b5d9b1c22",
        "report_type": "dashboard_pdf",
        "recipient_emails": ["user@example.test"],
    }
    ScheduledReportRequest(**base, frequency="daily")
    with pytest.raises(ValidationError):
        ScheduledReportRequest(**base, frequency="hourly")


def test_membership_email_is_bounded():
    with pytest.raises(ValidationError):
        AddMembershipRequest(
            org_id="6f1b7d5d-2c0a-4b9f-9a6d-7a0b5d9b1c22",
            user_email="x" * 256,
            role="accountant",
        )
