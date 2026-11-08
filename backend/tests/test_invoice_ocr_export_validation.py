"""Regression tests for malformed OCR invoice export payloads."""

import pytest
from fastapi import HTTPException
from uuid import uuid4

from app.services.invoice_ocr_engine import invoices_to_excel
from app.routers import invoice_ocr


@pytest.mark.parametrize("invoices", [None, {}, "invoice", [None], [1], ["invoice"]])
def test_invoice_export_rejects_non_object_invoice_records(invoices):
    with pytest.raises(ValueError, match="Invoices must be provided as a list|must be an object"):
        invoices_to_excel(invoices)


@pytest.mark.parametrize("line_items", [0, 1, "one", {}, {"item": "x"}])
def test_invoice_export_rejects_non_list_line_items(line_items):
    with pytest.raises(ValueError, match="line_items must be a list"):
        invoices_to_excel([{"vendor_name": "Sample Vendor", "line_items": line_items}])


def test_invoice_export_treats_missing_line_items_as_empty():
    workbook = invoices_to_excel([{"vendor_name": "Sample Vendor"}])
    assert workbook.startswith(b"PK")


def test_export_endpoint_maps_malformed_legacy_session_to_422():
    session_id = str(uuid4())
    org_id = str(uuid4())
    user_id = str(uuid4())
    invoice_ocr._EXTRACTED_INVOICES[session_id] = {
        "invoice": {"vendor_name": "Sample Vendor", "line_items": "malformed"},
        "org_id": org_id,
        "user_id": user_id,
    }

    try:
        with pytest.raises(HTTPException) as exc:
            invoice_ocr.export_to_excel(session_id, org_id=org_id, _user=user_id)
    finally:
        invoice_ocr._EXTRACTED_INVOICES.pop(session_id, None)

    assert exc.value.status_code == 422
    assert "line_items must be a list" in exc.value.detail
