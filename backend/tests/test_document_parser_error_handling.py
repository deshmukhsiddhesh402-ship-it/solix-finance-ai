import zipfile

import pytest
from docx.opc.exceptions import PackageNotFoundError
from openpyxl.utils.exceptions import InvalidFileException
from pypdf.errors import PdfReadError, PdfStreamError

from app.services import document_engine


@pytest.mark.parametrize("error", [PdfReadError("invalid PDF"), PdfStreamError("invalid PDF stream"), EOFError("empty PDF")])
def test_malformed_pdf_errors_are_normalized(monkeypatch, error):
    def fail(_file_bytes):
        raise error

    monkeypatch.setattr(document_engine, "extract_text_from_pdf", fail)
    with pytest.raises(ValueError, match="Invalid or unreadable PDF document") as exc_info:
        document_engine.extract_text("statement.pdf", b"invalid")
    assert exc_info.value.__cause__ is error


@pytest.mark.parametrize("error", [zipfile.BadZipFile("invalid archive"), InvalidFileException("invalid workbook"), KeyError("missing workbook part")])
def test_malformed_excel_errors_are_normalized(monkeypatch, error):
    def fail(_file_bytes):
        raise error

    monkeypatch.setattr(document_engine, "extract_text_from_xlsx", fail)
    with pytest.raises(ValueError, match="Invalid or unreadable Excel document") as exc_info:
        document_engine.extract_text("ledger.xlsx", b"invalid")
    assert exc_info.value.__cause__ is error


@pytest.mark.parametrize("error", [zipfile.BadZipFile("invalid archive"), PackageNotFoundError("invalid package"), KeyError("missing document part")])
def test_malformed_docx_errors_are_normalized(monkeypatch, error):
    def fail(_file_bytes):
        raise error

    monkeypatch.setattr(document_engine, "extract_text_from_docx", fail)
    with pytest.raises(ValueError, match="Invalid or unreadable Word document") as exc_info:
        document_engine.extract_text("invoice.docx", b"invalid")
    assert exc_info.value.__cause__ is error


def test_unexpected_parser_programming_errors_are_not_swallowed(monkeypatch):
    def fail(_file_bytes):
        raise RuntimeError("unexpected parser bug")

    monkeypatch.setattr(document_engine, "extract_text_from_xlsx", fail)
    with pytest.raises(RuntimeError, match="unexpected parser bug"):
        document_engine.extract_text("ledger.xlsx", b"invalid")
