import asyncio

import pytest

from app.services.request_body_engine import RequestBodyTooLargeError, read_stream_limited


async def chunks(*values):
    for value in values:
        yield value


def test_stream_reader_accepts_body_at_exact_limit():
    assert asyncio.run(read_stream_limited(chunks(b"123", b"45"), 5)) == b"12345"


def test_stream_reader_rejects_oversized_body_before_accumulating_extra_chunk():
    with pytest.raises(RequestBodyTooLargeError):
        asyncio.run(read_stream_limited(chunks(b"123", b"456"), 5))


@pytest.mark.parametrize("limit", [0, -1, True, 1.2])
def test_stream_reader_rejects_invalid_limit(limit):
    with pytest.raises(ValueError, match="max_bytes"):
        asyncio.run(read_stream_limited(chunks(b"x"), limit))
