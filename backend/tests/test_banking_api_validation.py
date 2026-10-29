"""API regression tests for bank reconciliation validation errors."""
import pytest
from fastapi import HTTPException

from app.routers import banking


def test_reconciliation_engine_value_error_becomes_http_422(monkeypatch):
    def reject_invalid_inputs(*args, **kwargs):
        raise ValueError("bank line identifiers must be unique.")

    monkeypatch.setattr(banking, "reconcile", reject_invalid_inputs)
    request = banking.ReconcileRequest(bank_lines=[], book_lines=[])

    with pytest.raises(HTTPException) as exc:
        banking.reconcile_endpoint(request, org_id="test-org", _user="test-user")

    assert exc.value.status_code == 422
    assert "identifiers must be unique" in exc.value.detail
