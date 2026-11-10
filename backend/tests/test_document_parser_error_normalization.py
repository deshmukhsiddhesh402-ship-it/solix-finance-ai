"""Regression tests for safe document parser error normalization."""
import pytest

from app.services import document_engine


@pytest.mark.parametrize(
    ("filename", "extractor_name"),
    [
        ("corrupt.pdf", "extract_text_from_pdf"),
        ("corrupt.xlsx", "extract_text_from_xlsx"),
        ("corrupt.docx", "extract_text_from_docx"),
    ],
)
def test_document_parser_failures_become_controlled_validation_errors(
    monkeypatch, filename, extractor_name
):
    def fail_parser(*_args, **_kwargs):
        raise RuntimeError("private parser detail")

    monkeypatch.setattr(document_engine, extractor_name, fail_parser)

    with pytest.raises(ValueError, match="could not be parsed") as exc:
        document_engine.extract_text(filename, b"not a valid document")

    assert isinstance(exc.value.__cause__, RuntimeError)
    assert "private parser detail" not in str(exc.value)


@pytest.mark.parametrize("filename", [None, "", "   "])
def test_document_extraction_rejects_missing_filename(filename):
    with pytest.raises(ValueError, match="filename must be a non-empty string"):
        document_engine.extract_text(filename, b"content")


def test_document_extraction_preserves_unsupported_extension_validation():
    with pytest.raises(ValueError, match="Unsupported file type"):
        document_engine.extract_text("ledger.exe", b"content")


def test_document_extraction_preserves_resource_limit_validation(monkeypatch):
    def reject_large_pdf(_file_bytes):
        raise ValueError("PDF exceeds the 50-page document extraction limit.")

    monkeypatch.setattr(document_engine, "extract_text_from_pdf", reject_large_pdf)

    with pytest.raises(ValueError, match="50-page"):
        document_engine.extract_text("ledger.pdf", b"%PDF")
