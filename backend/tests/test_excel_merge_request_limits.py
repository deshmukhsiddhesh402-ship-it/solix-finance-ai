"""Regression tests for bounded Excel automation merge requests."""
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.routers.excel_automation import MergeRequest


def test_merge_request_rejects_empty_session_list():
    with pytest.raises(ValidationError):
        MergeRequest(session_ids=[])


def test_merge_request_rejects_oversized_session_list():
    session_ids = [f"00000000-0000-4000-8000-{i:012d}" for i in range(101)]
    with pytest.raises(ValidationError):
        MergeRequest(session_ids=session_ids)


@pytest.mark.parametrize("count", [1, 100])
def test_merge_request_accepts_supported_session_list_sizes(count):
    session_ids = [f"00000000-0000-4000-8000-{i:012d}" for i in range(count)]
    request = MergeRequest(session_ids=session_ids)
    assert len(request.session_ids) == count
