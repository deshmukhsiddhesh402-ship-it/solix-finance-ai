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


from app.routers.accounting import LedgerLineIn


def test_tax_tags_accept_bounded_values():
    line = LedgerLineIn(
        account_name="GST Input", account_type="asset", debit=1180, credit=0,
        gst_rate_pct=18, gst_type="CGST", gst_taxable_value=1000,
    )
    assert line.gst_rate_pct == 18
    assert line.gst_type == "CGST"


def test_tax_tags_reject_out_of_range_values():
    with pytest.raises(ValidationError):
        LedgerLineIn(
            account_name="GST Input", account_type="asset", debit=1180, credit=0,
            gst_rate_pct=101,
        )
    with pytest.raises(ValidationError):
        LedgerLineIn(
            account_name="TDS Payable", account_type="liability", debit=0, credit=1000,
            tds_rate=-1,
        )


from app.services.invoice_ocr_engine import pdf_pages_to_images


def test_ocr_pdf_page_cap_is_forwarded():
    import inspect
    assert inspect.signature(pdf_pages_to_images).parameters["max_pages"].default == 20


def test_ocr_session_rejects_cross_user_access():
    from fastapi import HTTPException
    import app.routers.invoice_ocr as ocr

    ocr._EXTRACTED_INVOICES["security-test-session"] = {
        "invoice": {"total_amount": 100},
        "org_id": "6f1b7d5d-2c0a-4b9f-9a6d-7a0b5d9b1c22",
        "user_id": "11111111-1111-4111-8111-111111111111",
    }
    try:
        with pytest.raises(HTTPException) as exc:
            ocr._get_session(
                "security-test-session",
                "6f1b7d5d-2c0a-4b9f-9a6d-7a0b5d9b1c22",
                "22222222-2222-4222-8222-222222222222",
            )
        assert exc.value.status_code == 403
    finally:
        ocr._EXTRACTED_INVOICES.pop("security-test-session", None)
