import app.routers.invoice_ocr as ocr


def test_ocr_session_expires_at_exact_ttl_boundary(monkeypatch):
    ocr._EXTRACTED_INVOICES.clear()
    ocr._EXTRACTED_INVOICES["expired"] = {"created_at": 100.0}
    monkeypatch.setattr(ocr, "OCR_SESSION_TTL_SECONDS", 30)
    ocr._purge_expired_sessions(now=130.0)
    assert "expired" not in ocr._EXTRACTED_INVOICES


def test_ocr_session_without_creation_timestamp_is_purged(monkeypatch):
    ocr._EXTRACTED_INVOICES.clear()
    ocr._EXTRACTED_INVOICES["missing-created-at"] = {}
    monkeypatch.setattr(ocr, "OCR_SESSION_TTL_SECONDS", 30)
    ocr._purge_expired_sessions(now=1000.0)
    assert "missing-created-at" not in ocr._EXTRACTED_INVOICES
