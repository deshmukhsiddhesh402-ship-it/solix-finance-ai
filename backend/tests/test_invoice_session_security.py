"""Regression tests for OCR session tenant/user isolation and expiry."""
import time
import uuid

import pytest
from fastapi import HTTPException

from app.routers import invoice_ocr


def put_session(monkeypatch, *, org_id, user_id, created_at=None):
    session_id = str(uuid.uuid4())
    monkeypatch.setitem(
        invoice_ocr._EXTRACTED_INVOICES,
        session_id,
        {
            "invoice": {"vendor": "Example"},
            "org_id": str(org_id),
            "user_id": str(user_id),
            "created_at": time.time() if created_at is None else created_at,
        },
    )
    return session_id


def test_invoice_session_rejects_different_organization(monkeypatch):
    owner_org, owner_user = uuid.uuid4(), uuid.uuid4()
    other_org = uuid.uuid4()
    session_id = put_session(monkeypatch, org_id=owner_org, user_id=owner_user)

    with pytest.raises(HTTPException) as exc_info:
        invoice_ocr._get_session(session_id, str(other_org), str(owner_user))

    assert exc_info.value.status_code == 403


def test_invoice_session_rejects_different_user(monkeypatch):
    owner_org, owner_user = uuid.uuid4(), uuid.uuid4()
    other_user = uuid.uuid4()
    session_id = put_session(monkeypatch, org_id=owner_org, user_id=owner_user)

    with pytest.raises(HTTPException) as exc_info:
        invoice_ocr._get_session(session_id, str(owner_org), str(other_user))

    assert exc_info.value.status_code == 403


def test_expired_invoice_session_is_not_accessible(monkeypatch):
    org_id, user_id = uuid.uuid4(), uuid.uuid4()
    session_id = put_session(
        monkeypatch,
        org_id=org_id,
        user_id=user_id,
        created_at=time.time() - invoice_ocr.OCR_SESSION_TTL_SECONDS - 1,
    )

    with pytest.raises(HTTPException) as exc_info:
        invoice_ocr._get_session(session_id, str(org_id), str(user_id))

    assert exc_info.value.status_code == 404
    assert session_id not in invoice_ocr._EXTRACTED_INVOICES
