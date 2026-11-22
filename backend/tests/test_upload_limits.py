from fastapi import HTTPException
import pytest

from app.services.upload_limits import reject_oversized_content_length


def test_missing_content_length_is_allowed():
    reject_oversized_content_length(None)


def test_invalid_content_length_is_rejected():
    with pytest.raises(HTTPException) as exc:
        reject_oversized_content_length("unknown")
    assert exc.value.status_code == 400


def test_negative_content_length_is_rejected():
    with pytest.raises(HTTPException) as exc:
        reject_oversized_content_length("-1")
    assert exc.value.status_code == 400


def test_oversized_content_length_is_rejected():
    with pytest.raises(HTTPException) as exc:
        reject_oversized_content_length(str(10 * 1024 * 1024 + 1))
    assert exc.value.status_code == 413


def test_limit_boundary_is_allowed():
    reject_oversized_content_length(str(10 * 1024 * 1024))
