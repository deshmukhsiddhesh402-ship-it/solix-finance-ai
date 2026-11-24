"""Bounded streaming request-body reads for webhook endpoints."""
from collections.abc import AsyncIterable


class RequestBodyTooLargeError(ValueError):
    """Raised when a streamed request body exceeds its configured limit."""


async def read_stream_limited(stream: AsyncIterable[bytes], max_bytes: int) -> bytes:
    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes <= 0:
        raise ValueError("max_bytes must be a positive integer")
    body = bytearray()
    async for chunk in stream:
        if len(body) + len(chunk) > max_bytes:
            raise RequestBodyTooLargeError(f"Request body exceeds the {max_bytes}-byte limit.")
        body.extend(chunk)
    return bytes(body)
