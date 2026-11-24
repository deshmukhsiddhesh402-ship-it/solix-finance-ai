import pytest
from pydantic import ValidationError

from app.services.banking_engine import (
    MAX_RECONCILIATION_LINES,
    reconcile,
)
from app.routers.banking import ReconcileRequest


def test_reconcile_rejects_excessive_input_batch_before_matching():
    lines = [None] * (MAX_RECONCILIATION_LINES + 1)
    with pytest.raises(ValueError, match="limited to"):
        reconcile(lines, [])


def test_reconcile_request_bounds_both_input_lists():
    with pytest.raises(ValidationError):
        ReconcileRequest(
            bank_lines=[{}] * 1001,
            book_lines=[],
        )
