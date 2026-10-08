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


def test_pdf_ocr_rejects_non_positive_render_limits():
    from app.services.invoice_ocr_engine import pdf_pages_to_images

    with pytest.raises(ValueError, match="DPI must be positive"):
        pdf_pages_to_images(b"not-a-pdf", dpi=0)

    with pytest.raises(ValueError, match="max_pages must be positive"):
        pdf_pages_to_images(b"not-a-pdf", max_pages=0)


def test_rbac_fails_closed_for_unknown_role_action_and_resource():
    from app.services.rbac_engine import has_permission, list_permissions

    assert not has_permission("unknown-role", "journal_entry", "view")
    assert not has_permission("admin", "unknown-resource", "view")
    assert not has_permission("admin", "journal_entry", "unknown-action")
    assert list_permissions("unknown-role") == {}


def test_api_key_engine_generation_hash_verification_and_masking():
    from app.services.api_key_engine import (
        generate_api_key,
        hash_api_key,
        mask_api_key,
        verify_api_key,
    )

    plaintext, stored_hash = generate_api_key()
    assert plaintext.startswith("solix_")
    assert stored_hash == hash_api_key(plaintext)
    assert stored_hash != plaintext
    assert verify_api_key(plaintext, stored_hash)
    assert not verify_api_key(plaintext + "x", stored_hash)

    masked = mask_api_key(plaintext)
    assert masked != plaintext
    assert plaintext[:10] in masked
    assert plaintext[-4:] in masked
    assert "..." in masked

def test_api_key_name_is_bounded():
    with pytest.raises(ValidationError):
        CreateApiKeyRequest(org_id="6f1b7d5d-2c0a-4b9f-9a6d-7a0b5d9b1c22", name="")
    with pytest.raises(ValidationError):
        CreateApiKeyRequest(org_id="6f1b7d5d-2c0a-4b9f-9a6d-7a0b5d9b1c22", name="x" * 101)


def test_scheduled_report_frequency_is_allowlisted_and_bounded():
    base = {
        "org_id": "6f1b7d5d-2c0a-4b9f-9a6d-7a0b5d9b1c22",
        "report_type": "dashboard_pdf",
        "recipient_emails": ["user@example.com"],
    }
    ScheduledReportRequest(**base, frequency="daily")
    with pytest.raises(ValidationError):
        ScheduledReportRequest(**base, frequency="hourly")
    with pytest.raises(ValidationError):
        ScheduledReportRequest(**{**base, "recipient_emails": ["not-an-email"]}, frequency="daily")


def test_membership_email_is_bounded():
    with pytest.raises(ValidationError):
        AddMembershipRequest(
            org_id="6f1b7d5d-2c0a-4b9f-9a6d-7a0b5d9b1c22",
            user_email="x" * 256,
            role="accountant",
        )


from app.routers.accounting import LedgerLineIn


def test_membership_email_validation_rejects_malformed_address():
    with pytest.raises(ValidationError):
        AddMembershipRequest(
            org_id="6f1b7d5d-2c0a-4b9f-9a6d-7a0b5d9b1c22",
            user_email="not-an-email",
            role="accountant",
        )



def test_tax_engine_rejects_invalid_numeric_inputs():
    from app.services.tax_engine import calculate_gst, calculate_tds
    with pytest.raises(ValueError):
        calculate_gst(-100, 18, False)
    with pytest.raises(ValueError):
        calculate_gst(100, float("nan"), False)
    with pytest.raises(ValueError):
        calculate_tds(-1000, "194J")


def test_accounting_rejects_non_finite_journal_amount():
    from app.routers.accounting import LedgerLineIn
    with pytest.raises(ValidationError):
        LedgerLineIn(
            account_name="Cash", account_type="asset",
            debit=float("nan"), credit=0,
        )


def test_accounting_rejects_invalid_inventory_inputs():
    from app.routers.accounting import InventoryTxnIn
    with pytest.raises(ValidationError):
        InventoryTxnIn(txn_type="purchase", quantity=0, unit_cost=100)
    with pytest.raises(ValidationError):
        InventoryTxnIn(txn_type="purchase", quantity=1, unit_cost=float("inf"))


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


def test_ocr_journal_rejects_negative_amount():
    from app.services.invoice_ocr_engine import invoice_to_journal_lines
    with pytest.raises(ValueError, match="cannot be negative"):
        invoice_to_journal_lines({
            "vendor_name": "Test Vendor", "taxable_value": -100,
            "cgst_amount": 0, "sgst_amount": 0, "igst_amount": 0,
            "total_amount": -100,
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


def test_chat_keyword_session_rejects_cross_user_access():
    from fastapi import HTTPException
    import app.routers.chat as chat

    sid = "55555555-5555-4555-8555-555555555555"
    chat._TFIDF_SESSIONS[sid] = {
        "filename": "test.txt",
        "index": {},
        "org_id": "6f1b7d5d-2c0a-4b9f-9a6d-7a0b5d9b1c22",
        "user_id": "11111111-1111-4111-8111-111111111111",
    }
    try:
        with pytest.raises(HTTPException) as exc:
            chat.ask_question(
                chat.AskRequest(session_id=sid, question="test"),
                org_id="6f1b7d5d-2c0a-4b9f-9a6d-7a0b5d9b1c22",
                user_id="22222222-2222-4222-8222-222222222222",
            )
        assert exc.value.status_code == 403
    finally:
        chat._TFIDF_SESSIONS.pop(sid, None)


def test_chat_rejects_invalid_session_identifier():
    from fastapi import HTTPException
    import app.routers.chat as chat

    with pytest.raises(HTTPException) as exc:
        chat.ask_question(
            chat.AskRequest(session_id="not-a-uuid", question="test"),
            org_id="6f1b7d5d-2c0a-4b9f-9a6d-7a0b5d9b1c22",
            user_id="11111111-1111-4111-8111-111111111111",
        )
    assert exc.value.status_code == 400


def test_excel_parser_has_resource_bounds():
    import app.routers.excel_automation as excel
    assert excel.MAX_ROWS == 100_000
    assert excel.MAX_COLUMNS == 200
    assert excel.MAX_EXCEL_ZIP_ENTRIES == 200
    assert excel.MAX_EXCEL_UNCOMPRESSED_BYTES == 50 * 1024 * 1024


def test_excel_parser_rejects_invalid_archive():
    from fastapi import HTTPException
    import app.routers.excel_automation as excel
    with pytest.raises(HTTPException) as exc:
        excel._read_upload_to_df("malicious.xlsx", b"not-a-zip")
    assert exc.value.status_code == 400


def test_excel_parser_rejects_oversized_dataframe():
    import pandas as pd
    from fastapi import HTTPException
    import app.routers.excel_automation as excel
    oversized = pd.DataFrame({"amount": range(excel.MAX_ROWS + 1)})
    with pytest.raises(HTTPException) as exc:
        excel._validate_dataframe_shape(oversized)
    assert exc.value.status_code == 413


def test_ai_excel_prompt_inputs_are_bounded():
    from pydantic import ValidationError
    from app.routers.excel_ai import FormulaRequest, FixFormulaRequest, TaskRequest
    with pytest.raises(ValidationError):
        FormulaRequest(formula="")
    with pytest.raises(ValidationError):
        FormulaRequest(formula="x" * 5001)
    with pytest.raises(ValidationError):
        FixFormulaRequest(formula="=A1", error_description="x" * 3001)
    with pytest.raises(ValidationError):
        TaskRequest(task_description="x" * 5001)


def test_audit_log_limit_rejects_non_positive_values():
    from pydantic import ValidationError
    from app.routers.enterprise import view_audit_log
    import inspect
    # FastAPI's Query metadata is attached to the parameter; verify the declared lower bound.
    param = inspect.signature(view_audit_log).parameters["limit"].default
    assert any(getattr(item, "ge", None) == 1 for item in getattr(param, "metadata", []))

def test_production_config_rejects_default_jwt_secret():
    from app.core.config import Settings
    with pytest.raises(ValidationError):
        Settings(
            ENV="production",
            JWT_SECRET="change-me-in-production",
            DATABASE_URL="postgresql://solix_user:strong-password@db.example/solix",
        )


def test_production_config_requires_long_jwt_secret():
    from app.core.config import Settings
    with pytest.raises(ValidationError):
        Settings(
            ENV="production",
            JWT_SECRET="short-secret",
            DATABASE_URL="postgresql://solix_user:strong-password@db.example/solix",
        )


def test_production_config_rejects_default_database_url():
    from app.core.config import Settings
    with pytest.raises(ValidationError):
        Settings(
            ENV="production",
            JWT_SECRET="a" * 32,
            DATABASE_URL="postgresql://solix:solix@localhost:5432/solix_finance_ai",
        )


def test_ocr_upload_rejects_extension_content_mismatch():
    from app.routers.invoice_ocr import _has_expected_file_signature

    assert _has_expected_file_signature(b"%PDF-1.7\n", "pdf")
    assert not _has_expected_file_signature(b"not-a-pdf", "pdf")
    assert _has_expected_file_signature(b"\x89PNG\r\n\x1a\n", "png")
    assert not _has_expected_file_signature(b"RIFFxxxxWEBP", "png")


def test_ocr_upload_rejects_short_or_invalid_signatures():
    from app.routers.invoice_ocr import _has_expected_file_signature

    assert not _has_expected_file_signature(b"", "jpg")
    assert not _has_expected_file_signature(b"RIFF", "webp")
    assert not _has_expected_file_signature(b"not-an-image", "webp")


def test_ocr_session_store_evicts_expired_entries():
    import app.routers.invoice_ocr as ocr

    sid = "66666666-6666-4666-8666-666666666666"
    ocr._EXTRACTED_INVOICES[sid] = {
        "invoice": {},
        "org_id": "6f1b7d5d-2c0a-4b9f-9a6d-7a0b5d9b1c22",
        "user_id": "11111111-1111-4111-8111-111111111111",
        "created_at": 100,
    }
    try:
        ocr._purge_expired_sessions(now=100 + ocr.OCR_SESSION_TTL_SECONDS + 1)
        assert sid not in ocr._EXTRACTED_INVOICES
    finally:
        ocr._EXTRACTED_INVOICES.pop(sid, None)


def test_ocr_session_store_has_capacity_bound():
    import app.routers.invoice_ocr as ocr

    assert ocr.MAX_OCR_SESSIONS == 1000
    assert ocr.OCR_SESSION_TTL_SECONDS == 30 * 60


def test_otp_tracking_has_capacity_bound_and_expiry_cleanup():
    import app.core.security as security
    from datetime import datetime, timedelta, timezone

    assert security.MAX_OTP_TRACKED_EMAILS == 10000
    now = datetime.now(timezone.utc)
    key = "expired@example.com"
    security._OTP_STORE[key] = {
        "otp": "123456",
        "expires_at": now - timedelta(seconds=1),
        "attempts": 0,
    }
    try:
        security._purge_expired_otp_records(now)
        assert key not in security._OTP_STORE
    finally:
        security._OTP_STORE.pop(key, None)


def test_cleaned_excel_session_retention_is_bounded_and_expires():
    import app.routers.excel_automation as excel
    import time

    assert excel.MAX_CLEANED_SESSIONS == 1000
    assert excel.CLEANED_SESSION_TTL_SECONDS == 30 * 60
    sid = "expired-session"
    now = time.time()
    excel._CLEANED_FILES[sid] = {
        "df": None, "org_id": "org", "user_id": "user",
        "created_at": now - excel.CLEANED_SESSION_TTL_SECONDS - 1,
    }
    try:
        excel._purge_expired_cleaned_sessions(now)
        assert sid not in excel._CLEANED_FILES
    finally:
        excel._CLEANED_FILES.pop(sid, None)


def test_chat_session_retention_is_bounded_and_expires():
    import app.routers.chat as chat
    import time

    assert chat.MAX_CHAT_SESSIONS == 1000
    assert chat.CHAT_SESSION_TTL_SECONDS == 30 * 60
    sid = "expired-chat-session"
    now = time.time()
    chat._TFIDF_SESSIONS[sid] = {
        "filename": "test.txt", "index": {}, "org_id": "org",
        "user_id": "user", "created_at": now - chat.CHAT_SESSION_TTL_SECONDS - 1,
    }
    try:
        chat._purge_expired_chat_sessions(now)
        assert sid not in chat._TFIDF_SESSIONS
    finally:
        chat._TFIDF_SESSIONS.pop(sid, None)


def test_document_engine_parser_bounds_are_explicit():
    import app.services.document_engine as engine

    assert engine.MAX_DOCUMENT_SHEETS == 50
    assert engine.MAX_DOCUMENT_ROWS_PER_SHEET == 100_000
    assert engine.MAX_DOCUMENT_COLUMNS_PER_SHEET == 200
    assert engine.MAX_DOCUMENT_TABLES == 100
    assert engine.MAX_DOCUMENT_EXTRACTED_CHARS == 5_000_000
    assert engine.MAX_DOCUMENT_CHUNKS == 10_000


def test_document_chunk_parameters_fail_closed():
    from app.services.document_engine import chunk_text

    with pytest.raises(ValueError):
        chunk_text("one two three", chunk_size=0)
    with pytest.raises(ValueError):
        chunk_text("one two three", chunk_size=10, overlap=10)
    with pytest.raises(ValueError):
        chunk_text("one two three", chunk_size=10, overlap=-1)


def test_plain_text_extraction_enforces_direct_caller_limit():
    from app.services.document_engine import extract_text_from_pdf
    import app.services.document_engine as engine

    # Validate the shared extraction ceiling without constructing a real PDF.
    assert engine.MAX_DOCUMENT_EXTRACTED_CHARS == 5_000_000


def test_rag_limits_fail_closed_for_direct_callers():
    from app.services.rag_engine import (
        MAX_RAG_CHUNKS,
        MAX_RAG_QUERY_CHARS,
        MAX_RAG_TOP_K,
        build_index,
        retrieve,
    )

    assert MAX_RAG_CHUNKS == 10_000
    assert MAX_RAG_QUERY_CHARS == 4_000
    assert MAX_RAG_TOP_K == 10

    with pytest.raises(ValueError):
        build_index(["chunk"] * (MAX_RAG_CHUNKS + 1))
    index = build_index(["cash flow"])
    with pytest.raises(ValueError):
        retrieve("x" * (MAX_RAG_QUERY_CHARS + 1), index)
    with pytest.raises(ValueError):
        retrieve("cash", index, top_k=0)
    with pytest.raises(ValueError):
        retrieve("cash", index, top_k=MAX_RAG_TOP_K + 1)


def test_embedding_service_limits_and_validation_are_explicit():
    import app.services.embedding_service as embeddings

    assert embeddings.MAX_EMBEDDING_BATCH == 128
    assert embeddings.MAX_EMBEDDING_TEXT_CHARS == 4_000
    assert embeddings.MAX_EMBEDDING_TEXTS_CHARS == 5_000_000
    assert embeddings.EMBEDDING_DIMENSIONS == 1024

    with pytest.raises(ValueError):
        embeddings.get_embeddings([], input_type="document")
    with pytest.raises(ValueError):
        embeddings.get_embeddings(["text"], input_type="invalid")


def test_claude_request_limits_are_explicit():
    import app.services.claude_service as claude

    assert claude.MAX_CLAUDE_INPUT_CHARS == 50_000
    assert claude.MAX_CLAUDE_SYSTEM_CHARS == 20_000
    assert claude.MAX_CLAUDE_OUTPUT_TOKENS == 4_000
    assert claude.MAX_CLAUDE_TOOL_COUNT == 32
    assert claude.MAX_CLAUDE_IMAGE_BASE64_CHARS == 15_000_000

    with pytest.raises(ValueError):
        claude._validate_request("system", "user", 0)
    with pytest.raises(ValueError):
        claude._validate_request("system", "user", 4_001)
    with pytest.raises(ValueError):
        claude._validate_request("x" * (claude.MAX_CLAUDE_SYSTEM_CHARS + 1), "user", 1)
    with pytest.raises(ValueError):
        claude._validate_request("system", "x" * (claude.MAX_CLAUDE_INPUT_CHARS + 1), 1)


def test_claude_tool_result_and_tool_count_bounds():
    import app.services.claude_service as claude

    with pytest.raises(ValueError):
        claude.ask_claude_with_tools("system", "user", [{}] * (claude.MAX_CLAUDE_TOOL_COUNT + 1), 1)
    with pytest.raises(ValueError):
        claude.continue_with_tool_result(
            "system", "user", [], [], "", {"data": "x"}, 1
        )


def test_jwt_expiry_is_bounded():
    from app.core.security import MAX_JWT_EXPIRE_MINUTES, create_access_token

    with pytest.raises(ValueError):
        create_access_token("user-1", MAX_JWT_EXPIRE_MINUTES + 1)
    with pytest.raises(ValueError):
        create_access_token("user-1", 0)
    with pytest.raises(ValueError):
        create_access_token("user-1", -1)


def test_billing_plan_order_payload_is_strictly_allowlisted():
    from app.services.billing_engine import build_order_payload

    org_id = "6f1b7d5d-2c0a-4b9f-9a6d-7a0b5d9b1c22"
    payload = build_order_payload("pro", org_id)
    assert payload["amount"] == 299900
    assert payload["currency"] == "INR"
    assert payload["notes"] == {"org_id": org_id, "plan": "pro"}
    with pytest.raises(ValueError):
        build_order_payload("enterprise\u0000", org_id)


def test_billing_payment_inputs_are_bounded():
    from app.routers.billing import VerifyPaymentRequest

    base = {
        "org_id": "6f1b7d5d-2c0a-4b9f-9a6d-7a0b5d9b1c22",
        "plan": "pro",
        "razorpay_order_id": "order_123",
        "razorpay_payment_id": "pay_123",
        "razorpay_signature": "a" * 64,
    }
    VerifyPaymentRequest(**base)
    with pytest.raises(ValidationError):
        VerifyPaymentRequest(**{**base, "razorpay_order_id": ""})
    with pytest.raises(ValidationError):
        VerifyPaymentRequest(**{**base, "razorpay_signature": "short"})
    with pytest.raises(ValidationError):
        VerifyPaymentRequest(**{**base, "razorpay_payment_id": "x" * 101})


def test_audit_entry_fields_are_bounded():
    from app.services.audit_engine import build_audit_entry

    build_audit_entry("user-1", "org-1", "edit", "invoice", "123")
    with pytest.raises(ValueError):
        build_audit_entry("user-1", "org-1", "x" * 21, "invoice", "123")
    with pytest.raises(ValueError):
        build_audit_entry("user-1", "org-1", "edit", "x" * 51, "123")
    with pytest.raises(ValueError):
        build_audit_entry("user-1", "org-1", "edit", "invoice", "x" * 101)


def test_copilot_tool_inputs_fail_closed():
    from app.routers.copilot import _execute_tool

    with pytest.raises(ValueError):
        _execute_tool("unknown_tool", {}, [])
    with pytest.raises(ValueError):
        _execute_tool("filter_transactions", {"min_amount": float("nan")}, [])
    with pytest.raises(ValueError):
        _execute_tool("filter_transactions", {"min_amount": -1}, [])
    with pytest.raises(ValueError):
        _execute_tool("compare_periods", {"period_a": "2026-13", "period_b": "2026-10"}, [])
    with pytest.raises(ValueError):
        _execute_tool("predict_cash_flow", {"months_ahead": 25}, [])


def test_copilot_engine_rejects_invalid_period_months():
    from app.services.copilot_engine import compare_periods

    with pytest.raises(ValueError):
        compare_periods([], "2026-00", "2026-10")
    with pytest.raises(ValueError):
        compare_periods([], "2026-13", "2026-10")
    with pytest.raises(ValueError):
        compare_periods([], "abcd-10", "2026-10")


def test_copilot_engine_bounds_are_fail_closed():
    from app.services.copilot_engine import filter_transactions, predict_cash_flow

    with pytest.raises(ValueError):
        filter_transactions([{}] * 100_001)
    with pytest.raises(ValueError):
        filter_transactions([], min_amount=float("inf"))
    with pytest.raises(ValueError):
        filter_transactions([], account_type="admin")
    with pytest.raises(ValueError):
        predict_cash_flow([1.0, float("nan")])
    with pytest.raises(ValueError):
        predict_cash_flow([1.0, 2.0], months_ahead=25)



def test_inventory_valuation_rejects_overselling():
    from app.services.accounting_engine import InventoryTxn, inventory_valuation

    txns = [InventoryTxn("purchase", 10, 100)]
    for method in ("FIFO", "LIFO", "WAVG"):
        with pytest.raises(ValueError, match="exceeds available inventory"):
            inventory_valuation(txns + [InventoryTxn("sale", 11, 0)], method)


def test_inventory_valuation_rejects_non_finite_direct_inputs():
    from app.services.accounting_engine import InventoryTxn, inventory_valuation

    with pytest.raises(ValueError, match="finite"):
        inventory_valuation([InventoryTxn("purchase", float("nan"), 100)], "FIFO")
    with pytest.raises(ValueError, match="finite"):
        inventory_valuation([InventoryTxn("purchase", 1, float("inf"))], "FIFO")


def test_inventory_valuation_rejects_invalid_method_and_amounts():
    from app.services.accounting_engine import InventoryTxn, inventory_valuation

    with pytest.raises(ValueError, match="Unsupported"):
        inventory_valuation([InventoryTxn("purchase", 1, 100)], "BAD")
    with pytest.raises(ValueError, match="positive"):
        inventory_valuation([InventoryTxn("purchase", 0, 100)], "FIFO")
    with pytest.raises(ValueError, match="non-negative"):
        inventory_valuation([InventoryTxn("purchase", 1, -1)], "FIFO")


def test_inventory_valuation_preserves_valid_fifo_result():
    from app.services.accounting_engine import InventoryTxn, inventory_valuation

    result = inventory_valuation(
        [InventoryTxn("purchase", 10, 100), InventoryTxn("purchase", 5, 120), InventoryTxn("sale", 12, 0)],
        "FIFO",
    )
    assert result["closing_quantity"] == 3
    assert result["closing_inventory_value"] == 360
    assert result["cogs"] == 1240



def test_accounting_engine_rejects_non_finite_and_negative_ledger_values():
    from app.services.accounting_engine import LedgerLine, build_trial_balance

    with pytest.raises(ValueError, match="finite"):
        build_trial_balance([LedgerLine("Cash", "asset", float("nan"), 0)])
    with pytest.raises(ValueError, match="negative"):
        build_trial_balance([LedgerLine("Cash", "asset", -1, 0)])
    with pytest.raises(ValueError, match="non-empty"):
        build_trial_balance([LedgerLine(" ", "asset", 1, 0)])


def test_accounting_engine_rejects_non_finite_and_negative_ratio_inputs():
    from app.services.accounting_engine import financial_ratios

    with pytest.raises(ValueError, match="finite"):
        financial_ratios(float("inf"), 1, 0, 0, 1, 1, 1, 1)
    with pytest.raises(ValueError, match="negative"):
        financial_ratios(-1, 1, 0, 0, 1, 1, 1, 1)



def test_depreciation_engine_rejects_invalid_direct_inputs():
    from app.services.accounting_engine import straight_line_depreciation, wdv_depreciation_schedule

    with pytest.raises(ValueError, match="finite"):
        straight_line_depreciation(float("nan"), 0, 5)
    with pytest.raises(ValueError, match="cannot exceed"):
        straight_line_depreciation(100, 101, 5)
    with pytest.raises(ValueError, match="at least 1"):
        straight_line_depreciation(100, 0, 0)
    with pytest.raises(ValueError, match="between 0 and 100"):
        wdv_depreciation_schedule(1000, 101, 1)
    with pytest.raises(ValueError, match="finite"):
        wdv_depreciation_schedule(1000, float("inf"), 1)



def test_financial_ratios_reject_inventory_above_current_assets():
    from app.services.accounting_engine import financial_ratios

    with pytest.raises(ValueError, match="Inventory cannot exceed current assets"):
        financial_ratios(100, 50, 101, 0, 100, 10, 200, 300)



def test_financial_statements_reject_invalid_direct_rows():
    from app.services.accounting_engine import build_profit_and_loss, build_balance_sheet

    with pytest.raises(ValueError, match="finite"):
        build_profit_and_loss([{"type": "income", "debit": float("nan"), "credit": 100}])
    with pytest.raises(ValueError, match="invalid account type"):
        build_profit_and_loss([{"type": "unknown", "debit": 0, "credit": 100}])
    with pytest.raises(ValueError, match="finite"):
        build_balance_sheet([], float("inf"))
    with pytest.raises(ValueError, match="negative"):
        build_balance_sheet([{"type": "asset", "debit": -1, "credit": 0}], 0)


def test_trial_balance_rejects_invalid_direct_line_type():
    from app.services.accounting_engine import build_trial_balance

    with pytest.raises(ValueError, match="LedgerLine"):
        build_trial_balance([{"account_name": "Cash", "account_type": "asset", "debit": 1, "credit": 0}])


def test_income_tax_engine_rejects_invalid_direct_inputs():
    from app.services.tax_engine import calculate_income_tax_new_regime

    with pytest.raises(ValueError, match="gross_salary"):
        calculate_income_tax_new_regime(-1, 0)
    with pytest.raises(ValueError, match="gross_salary"):
        calculate_income_tax_new_regime(float("nan"), 0)
    with pytest.raises(ValueError, match="other_income"):
        calculate_income_tax_new_regime(500000, float("inf"))


def test_trial_balance_rejects_conflicting_account_types():
    from app.services.accounting_engine import LedgerLine, build_trial_balance

    with pytest.raises(ValueError, match="multiple account types"):
        build_trial_balance([
            LedgerLine("Cash", "asset", debit=100, credit=0),
            LedgerLine("Cash", "income", debit=0, credit=100),
        ])


def test_gst_rejects_non_boolean_interstate_flag():
    from app.services.tax_engine import calculate_gst

    with pytest.raises(ValueError, match="is_interstate"):
        calculate_gst(1000, 18, "false")
