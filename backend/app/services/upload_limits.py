"""Upload-size validation helpers shared by document endpoints."""
from fastapi import HTTPException

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def reject_oversized_content_length(content_length: str | None, *, max_bytes: int = MAX_UPLOAD_BYTES) -> None:
    """Fail early when a declared request body exceeds the endpoint limit.

    Chunked requests without Content-Length are still checked after reading the
    body; this helper only prevents avoidable large allocations for declared
    sizes.
    """
    if content_length is None:
        return
    try:
        declared = int(content_length)
    except (TypeError, ValueError) as exc:
        raise HTTPException(400, detail="Invalid Content-Length header.") from exc
    if declared < 0:
        raise HTTPException(400, detail="Invalid Content-Length header.")
    if declared > max_bytes:
        raise HTTPException(413, detail=f"Uploaded document exceeds the {max_bytes // (1024 * 1024)} MB limit.")
