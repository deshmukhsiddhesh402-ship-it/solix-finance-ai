import pytest

from app.services.upload_names import safe_upload_filename


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("../../invoice.pdf", "invoice.pdf"),
        ("folder\\invoice.pdf", "invoice.pdf"),
        ("\x00invoice\n.pdf", "invoice.pdf"),
        ("   ", "uploaded-document"),
        (None, "uploaded-document"),
    ],
)
def test_safe_upload_filename_removes_path_and_control_characters(raw, expected):
    assert safe_upload_filename(raw) == expected


def test_safe_upload_filename_is_bounded():
    assert len(safe_upload_filename("a" * 300 + ".pdf")) == 255
