"""Scheduled report request validation regression tests."""
import pytest
from pydantic import ValidationError

from app.routers.enterprise import ScheduledReportRequest


def test_scheduled_report_normalizes_report_type_whitespace():
    request = ScheduledReportRequest(
        org_id="00000000-0000-0000-0000-000000000001",
        report_type="  dashboard_pdf  ",
        frequency="weekly",
        recipient_emails=["finance@example.com"],
    )

    assert request.report_type == "dashboard_pdf"


def test_scheduled_report_rejects_blank_report_type():
    with pytest.raises(ValidationError, match="report_type must not be blank"):
        ScheduledReportRequest(
            org_id="00000000-0000-0000-0000-000000000001",
            report_type="   ",
            frequency="weekly",
            recipient_emails=["finance@example.com"],
        )


def test_scheduled_report_rejects_duplicate_recipient_addresses_case_insensitively():
    with pytest.raises(ValidationError, match="duplicate addresses"):
        ScheduledReportRequest(
            org_id="00000000-0000-0000-0000-000000000001",
            report_type="dashboard_pdf",
            frequency="weekly",
            recipient_emails=["Finance@example.com", "finance@EXAMPLE.com"],
        )


def test_scheduled_report_preserves_distinct_recipient_addresses():
    request = ScheduledReportRequest(
        org_id="00000000-0000-0000-0000-000000000001",
        report_type="dashboard_pdf",
        frequency="weekly",
        recipient_emails=["finance@example.com", "owner@example.com"],
    )

    assert len(request.recipient_emails) == 2
