from io import BytesIO
from zipfile import ZipFile

import pytest

import app.services.document_engine as documents


def _zip_with_entries(entries):
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        for name, value in entries:
            archive.writestr(name, value)
    return buffer.getvalue()


def test_document_xlsx_archive_rejects_invalid_zip():
    with pytest.raises(ValueError, match="Invalid XLSX"):
        documents._validate_xlsx_archive(b"not-a-zip")


def test_document_xlsx_archive_rejects_too_many_entries(monkeypatch):
    monkeypatch.setattr(documents, "MAX_DOCUMENT_XLSX_ZIP_ENTRIES", 1)
    payload = _zip_with_entries([("a", "1"), ("b", "2")])
    with pytest.raises(ValueError, match="archive-entry"):
        documents._validate_xlsx_archive(payload)


def test_document_xlsx_archive_rejects_excessive_expansion(monkeypatch):
    monkeypatch.setattr(documents, "MAX_DOCUMENT_XLSX_UNCOMPRESSED_BYTES", 4)
    payload = _zip_with_entries([("xl/sharedStrings.xml", "12345")])
    with pytest.raises(ValueError, match="expands"):
        documents._validate_xlsx_archive(payload)


def test_document_xlsx_archive_accepts_bounded_container():
    payload = _zip_with_entries([("xl/workbook.xml", "<workbook/>")])
    documents._validate_xlsx_archive(payload)
