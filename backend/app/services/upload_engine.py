"""Bounded streaming reads for user-uploaded files.

Read at most max_bytes + 1 bytes so oversized chunked uploads are rejected
without buffering the complete request body in application memory.
"""
from typing import Protocol


class UploadTooLargeError(ValueError):
    """Raised when an uploaded file exceeds its configured byte limit."""


class AsyncReadableUpload(Protocol):
    async def read(self, size: int = -1) -> bytes: ...


async def read_upload_limited(upload: AsyncReadableUpload, max_bytes: int) -> bytes:
    """Read an upload with a strict memory bound and fail when it is too large."""
    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes <= 0:
        raise ValueError("max_bytes must be a positive integer")
    content = await upload.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise UploadTooLargeError(f"Upload exceeds the {max_bytes}-byte limit.")
    return content
