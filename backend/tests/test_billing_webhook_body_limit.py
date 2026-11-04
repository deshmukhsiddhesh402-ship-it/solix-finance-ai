import asyncio

import pytest
from fastapi import HTTPException

from app.routers.billing import _parse_webhook_payload, _read_bounded_webhook_body


class ChunkedRequest:
    def __init__(self, chunks):
        self.chunks = chunks

    async def stream(self):
        for chunk in self.chunks:
            yield chunk


def test_webhook_body_reader_accepts_payload_at_exact_limit():
    body = asyncio.run(_read_bounded_webhook_body(ChunkedRequest([b"abc", b"def"]), 6))
    assert body == b"abcdef"


def test_webhook_body_reader_rejects_oversized_stream_before_joining():
    request = ChunkedRequest([b"abc", b"def", b"ghi"])

    with pytest.raises(HTTPException) as exc:
        asyncio.run(_read_bounded_webhook_body(request, 5))

    assert exc.value.status_code == 413
    assert exc.value.detail == "Webhook payload is too large."


@pytest.mark.parametrize("limit", [0, -1, True, 1.5])
def test_webhook_body_reader_requires_positive_integer_limit(limit):
    with pytest.raises(ValueError, match="positive integer"):
        asyncio.run(_read_bounded_webhook_body(ChunkedRequest([b"x"]), limit))


class BodyOnlyRequest:
    def __init__(self, body):
        self._body = body

    async def body(self):
        return self._body


def test_webhook_body_reader_supports_body_only_request_adapters():
    body = asyncio.run(_read_bounded_webhook_body(BodyOnlyRequest(b"adapter-body"), 20))
    assert body == b"adapter-body"


def test_webhook_body_reader_rejects_oversized_body_only_request_adapters():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(_read_bounded_webhook_body(BodyOnlyRequest(b"too-large"), 3))

    assert exc.value.status_code == 413
    assert exc.value.detail == "Webhook payload is too large."


def test_webhook_payload_parser_accepts_json_objects():
    assert _parse_webhook_payload('{"event":"payment.failed"}') == {"event": "payment.failed"}


def test_webhook_payload_parser_rejects_invalid_json():
    with pytest.raises(HTTPException) as exc:
        _parse_webhook_payload("{")

    assert exc.value.status_code == 400
    assert exc.value.detail == "Webhook payload is not valid JSON."


def test_webhook_payload_parser_rejects_non_object_json():
    with pytest.raises(HTTPException) as exc:
        _parse_webhook_payload("[]")

    assert exc.value.status_code == 400
    assert exc.value.detail == "Webhook payload must be a JSON object."
