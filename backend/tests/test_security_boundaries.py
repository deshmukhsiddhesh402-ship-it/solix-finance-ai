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

    ocr._EXTRACTED_INVOICES["33333333-3333-4333-8333-333333333333"] = {
        "invoice": {"total_amount": 100},
        "org_id": "6f1b7d5d-2c0a-4b9f-9a6d-7a0b5d9b1c22",
        "user_id": "11111111-1111-4111-8111-111111111111",
    }
    try:
        with pytest.raises(HTTPException) as exc:
            ocr._get_session(
                "33333333-3333-4333-8333-333333333333",
                "6f1b7d5d-2c0a-4b9f-9a6d-7a0b5d9b1c22",
                "22222222-2222-4222-8222-222222222222",
            )
        assert exc.value.status_code == 403
    finally:
        ocr._EXTRACTED_INVOICES.pop("33333333-3333-4333-8333-333333333333", None)


def test_ocr_session_rejects_invalid_identifier():
    from fastapi import HTTPException
    import app.routers.invoice_ocr as ocr

    with pytest.raises(HTTPException) as exc:
        ocr._get_session("not-a-uuid", "6f1b7d5d-2c0a-4b9f-9a6d-7a0b5d9b1c22", "11111111-1111-4111-8111-111111111111")
    assert exc.value.status_code == 400


def test_ocr_journal_request_bounds_expense_account():
    from app.routers.invoice_ocr import JournalEntryRequest
    with pytest.raises(ValidationError):
        JournalEntryRequest(session_id="33333333-3333-4333-8333-333333333333", expense_account="x" * 256)


def test_ocr_journal_rejects_unreconciled_total():
    from app.services.invoice_ocr_engine import invoice_to_journal_lines
    with pytest.raises(ValueError, match="does not reconcile"):
        invoice_to_journal_lines({
            "vendor_name": "Test Vendor", "taxable_value": 100,
            "cgst_amount": 9, "sgst_amount": 9, "igst_amount": 0,
            "total_amount": 200,
        })


def test_ocr_journal_rejects_non_finite_amount():
    from app.services.invoice_ocr_engine import invoice_to_journal_lines
    with pytest.raises(ValueError, match="finite"):
        invoice_to_journal_lines({
            "vendor_name": "Test Vendor", "taxable_value": "nan",
            "cgst_amount": 0, "sgst_amount": 0, "igst_amount": 0,
            "total_amount": 0,
        })


def test_excel_session_rejects_cross_user_access():
    from fastapi import HTTPException
    import app.routers.excel_automation as excel

    sid = "44444444-4444-4444-8444-444444444444"
    excel._CLEANED_FILES[sid] = {
        "df": None,
        "org_id": "6f1b7d5d-2c0a-4b9f-9a6d-7a0b5d9b1c22",
        "user_id": "11111111-1111-4111-8111-111111111111",
    }
    try:
        with pytest.raises(HTTPException) as exc:
            excel._get_cleaned_session(
                sid,
                "6f1b7d5d-2c0a-4b9f-9a6d-7a0b5d9b1c22",
                "22222222-2222-4222-8222-222222222222",
            )
        assert exc.value.status_code == 403
    finally:
        excel._CLEANED_FILES.pop(sid, None)


def test_excel_upload_limit_is_bounded():
    import app.routers.excel_automation as excel
    assert excel.MAX_UPLOAD_BYTES == 10 * 1024 * 1024


def test_chat_upload_limit_is_bounded():
    import app.routers.chat as chat
    assert chat.MAX_UPLOAD_BYTES == 10 * 1024 * 1024
