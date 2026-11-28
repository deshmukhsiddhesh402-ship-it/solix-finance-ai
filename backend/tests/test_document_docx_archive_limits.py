from io import BytesIO
from zipfile import ZipFile

import pytest

import app.services.document_engine as documents


def _docx_zip(entries):
    stream = BytesIO()
    with ZipFile(stream, "w") as archive:
        for name, value in entries:
            archive.writestr(name, value)
    return stream.getvalue()


def test_docx_archive_rejects_malformed_zip():
    with pytest.raises(ValueError, match="Invalid DOCX"):
        documents._validate_docx_archive(b"invalid")


def test_docx_archive_rejects_excessive_entry_count(monkeypatch):
    monkeypatch.setattr(documents, "MAX_DOCUMENT_DOCX_ZIP_ENTRIES", 1)
    with pytest.raises(ValueError, match="archive-entry"):
        documents._validate_docx_archive(_docx_zip([("a", "1"), ("b", "2")]))


def test_docx_archive_rejects_excessive_uncompressed_size(monkeypatch):
    monkeypatch.setattr(documents, "MAX_DOCUMENT_DOCX_UNCOMPRESSED_BYTES", 3)
    with pytest.raises(ValueError, match="expands"):
        documents._validate_docx_archive(_docx_zip([("word/document.xml", "1234")]))


def test_docx_archive_accepts_small_container():
    documents._validate_docx_archive(_docx_zip([("word/document.xml", "<doc/>")]))
