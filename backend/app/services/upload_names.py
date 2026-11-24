"""Safe upload filename normalization shared by document endpoints."""
import re

_MAX_FILENAME_LENGTH = 255
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def safe_upload_filename(filename: str | None, *, fallback: str = "uploaded-document") -> str:
    """Return a bounded, display-safe filename without path/control characters."""
    value = (filename or "").replace("\\", "/").rsplit("/", 1)[-1]
    value = _CONTROL_CHARS.sub("", value).strip()
    if not value:
        return fallback
    return value[:_MAX_FILENAME_LENGTH]
