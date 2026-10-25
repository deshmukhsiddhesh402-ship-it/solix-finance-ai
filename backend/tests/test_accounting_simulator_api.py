"""API contract tests for the stateless accounting simulator."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.accounting_simulator import router

app = FastAPI()
app.include_router(router, prefix="/api/accounting-simulator")
client = TestClient(app)


def test_practice_journal_entry_returns_balanced_totals_without_persisting():
    response = client.post(
        "/api/accounting-simulator/practice/journal-entry",
        json={
            "narration": "Being capital introduced in cash",
            "lines": [
                {"account": "Cash", "debit": "1000.00"},
                {"account": "Capital", "credit": "1000.00"},
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "practice_only"
    assert body["persisted"] is False
    assert body["is_balanced"] is True
    assert body["total_debit"] == "1000.00"
    assert body["total_credit"] == "1000.00"


def test_practice_journal_entry_rejects_unbalanced_entry():
    response = client.post(
        "/api/accounting-simulator/practice/journal-entry",
        json={
            "lines": [
                {"account": "Cash", "debit": "1000.00"},
                {"account": "Capital", "credit": "999.00"},
            ],
        },
    )
    assert response.status_code == 422
    assert "unbalanced" in response.json()["detail"]


def test_practice_cycle_returns_ledger_and_balanced_trial_balance():
    response = client.post(
        "/api/accounting-simulator/practice/accounting-cycle",
        json={
            "entries": [
                {"lines": [
                    {"account": "Cash", "debit": "1000.00"},
                    {"account": "Capital", "credit": "1000.00"},
                ]},
                {"lines": [
                    {"account": "Rent Expense", "debit": "100.00"},
                    {"account": "Cash", "credit": "100.00"},
                ]},
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["persisted"] is False
    assert body["journal_entry_count"] == 2
    assert body["trial_balance"]["is_balanced"] is True
    assert body["trial_balance"]["total_debit"] == body["trial_balance"]["total_credit"]


def test_practice_cash_book_calculates_closing_balance():
    response = client.post(
        "/api/accounting-simulator/practice/cash-book",
        json={
            "opening_balance": "500.00",
            "receipts": [{"description": "Cash sales", "amount": "200.00"}],
            "payments": [{"description": "Office supplies", "amount": "75.00"}],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["persisted"] is False
    assert body["closing_balance"] == "625.00"


def test_practice_cash_book_rejects_cash_overdraft():
    response = client.post(
        "/api/accounting-simulator/practice/cash-book",
        json={
            "opening_balance": "100.00",
            "receipts": [],
            "payments": [{"description": "Payment", "amount": "101.00"}],
        },
    )
    assert response.status_code == 422


def test_request_size_limits_reject_oversized_cycle():
    response = client.post(
        "/api/accounting-simulator/practice/accounting-cycle",
        json={"entries": [{"lines": [
            {"account": f"Account {i}", "debit": "1.00"} for i in range(101)
        ]}]},
    )
    assert response.status_code == 422
