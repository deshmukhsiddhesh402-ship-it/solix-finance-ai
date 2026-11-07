"""Regression tests for malformed Claude responses in Finance Copilot."""
from pathlib import Path
from types import SimpleNamespace
import sys
from uuid import uuid4

import pytest
from fastapi import HTTPException

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.routers import copilot


def _invoke(monkeypatch, response):
    monkeypatch.setattr(copilot, "_load_entries_for_copilot", lambda *args: [])
    monkeypatch.setattr(copilot, "ask_claude_with_tools", lambda *args: response)
    request = copilot.CopilotRequest(question="Summarize my expenses")
    return copilot.ask_copilot(request, org_id=str(uuid4()), db=object(), _user="user-id")


@pytest.mark.parametrize("response", [None, SimpleNamespace(content=None), SimpleNamespace(content=())])
def test_copilot_rejects_missing_or_non_list_provider_content(monkeypatch, response):
    with pytest.raises(HTTPException) as exc:
        _invoke(monkeypatch, response)

    assert exc.value.status_code == 502
    assert "invalid response" in exc.value.detail


def test_copilot_rejects_non_text_text_block(monkeypatch):
    response = SimpleNamespace(content=[SimpleNamespace(type="text", text=123)])

    with pytest.raises(HTTPException) as exc:
        _invoke(monkeypatch, response)

    assert exc.value.status_code == 502
    assert "invalid text" in exc.value.detail


def test_copilot_rejects_empty_direct_answer(monkeypatch):
    response = SimpleNamespace(content=[SimpleNamespace(type="text", text="   ")])

    with pytest.raises(HTTPException) as exc:
        _invoke(monkeypatch, response)

    assert exc.value.status_code == 502
    assert "empty answer" in exc.value.detail


def test_copilot_rejects_multiple_tool_requests(monkeypatch):
    response = SimpleNamespace(content=[
        SimpleNamespace(type="tool_use", name="gst_summary", input={}, id="tool-1"),
        SimpleNamespace(type="tool_use", name="gst_summary", input={}, id="tool-2"),
    ])

    with pytest.raises(HTTPException) as exc:
        _invoke(monkeypatch, response)

    assert exc.value.status_code == 502
    assert "multiple tool requests" in exc.value.detail


def test_copilot_rejects_malformed_tool_request(monkeypatch):
    response = SimpleNamespace(content=[
        SimpleNamespace(type="tool_use", name="gst_summary", input=[], id="tool-1")
    ])

    with pytest.raises(HTTPException) as exc:
        _invoke(monkeypatch, response)

    assert exc.value.status_code == 502
    assert "invalid tool request" in exc.value.detail


def test_copilot_rejects_unsupported_tool_selected_by_provider(monkeypatch):
    response = SimpleNamespace(content=[
        SimpleNamespace(type="tool_use", name="drop_tenant_data", input={}, id="tool-1")
    ])

    with pytest.raises(HTTPException) as exc:
        _invoke(monkeypatch, response)

    assert exc.value.status_code == 502
    assert "unsupported tool request" in exc.value.detail


def test_copilot_maps_provider_request_exceptions_to_http_502(monkeypatch):
    monkeypatch.setattr(copilot, "_load_entries_for_copilot", lambda *args: [])

    def fail(*args):
        raise RuntimeError("provider detail should not leak")

    monkeypatch.setattr(copilot, "ask_claude_with_tools", fail)

    with pytest.raises(HTTPException) as exc:
        copilot.ask_copilot(
            copilot.CopilotRequest(question="Summarize my expenses"),
            org_id=str(uuid4()),
            db=object(),
            _user="user-id",
        )

    assert exc.value.status_code == 502
    assert "provider request failed" in exc.value.detail
    assert "provider detail" not in exc.value.detail


def test_copilot_returns_valid_direct_text_response(monkeypatch):
    response = SimpleNamespace(content=[SimpleNamespace(type="text", text="Expenses increased.")])

    result = _invoke(monkeypatch, response)

    assert result == {"answer": "Expenses increased.", "data": None}


def test_copilot_returns_valid_tool_result_and_final_answer(monkeypatch):
    response = SimpleNamespace(content=[
        SimpleNamespace(type="tool_use", name="gst_summary", input={}, id="tool-1")
    ])
    monkeypatch.setattr(copilot, "_execute_tool", lambda name, inputs, entries: {"total_tax": 123.0})
    monkeypatch.setattr(
        copilot,
        "continue_with_tool_result",
        lambda *args, **kwargs: "The calculated output tax is ₹123.",
    )

    result = _invoke(monkeypatch, response)

    assert result == {
        "answer": "The calculated output tax is ₹123.",
        "data": {"total_tax": 123.0},
        "tool_used": "gst_summary",
    }


def test_copilot_maps_follow_up_provider_exceptions_to_http_502(monkeypatch):
    response = SimpleNamespace(content=[
        SimpleNamespace(type="tool_use", name="gst_summary", input={}, id="tool-1")
    ])
    monkeypatch.setattr(copilot, "_execute_tool", lambda name, inputs, entries: {"total_tax": 123.0})

    def fail(*args, **kwargs):
        raise RuntimeError("provider detail should not leak")

    monkeypatch.setattr(copilot, "continue_with_tool_result", fail)

    with pytest.raises(HTTPException) as exc:
        _invoke(monkeypatch, response)

    assert exc.value.status_code == 502
    assert "follow-up request failed" in exc.value.detail
    assert "provider detail" not in exc.value.detail


def test_copilot_rejects_empty_final_answer(monkeypatch):
    response = SimpleNamespace(content=[
        SimpleNamespace(type="tool_use", name="gst_summary", input={}, id="tool-1")
    ])
    monkeypatch.setattr(copilot, "_execute_tool", lambda name, inputs, entries: {"total_tax": 123.0})
    monkeypatch.setattr(copilot, "continue_with_tool_result", lambda *args, **kwargs: "  ")

    with pytest.raises(HTTPException) as exc:
        _invoke(monkeypatch, response)

    assert exc.value.status_code == 502
    assert "empty final answer" in exc.value.detail
