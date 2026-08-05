"""
Module 7: AI Chat / RAG — document ingestion.

Extracts text from uploaded PDFs, Excel files, and plain text, then splits
it into overlapping chunks suitable for retrieval. Kept dependency-light:
pypdf for PDFs, openpyxl for Excel (both already in requirements.txt).
"""
import io
from openpyxl import load_workbook


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract plain text from a PDF's pages."""
    from pypdf import PdfReader  # local import: optional dependency, only needed here
    reader = PdfReader(io.BytesIO(file_bytes))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)


def extract_text_from_xlsx(file_bytes: bytes) -> str:
    """Flatten every sheet's cell values into readable text, row by row."""
    wb = load_workbook(io.BytesIO(file_bytes), data_only=True)
    lines = []
    for sheet in wb.worksheets:
        lines.append(f"--- Sheet: {sheet.title} ---")
        for row in sheet.iter_rows(values_only=True):
            cells = [str(c) for c in row if c is not None]
            if cells:
                lines.append(" | ".join(cells))
    return "\n".join(lines)


def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extract paragraph and table text from a Word document."""
    from docx import Document  # local import: optional dependency, only needed here
    doc = Document(io.BytesIO(file_bytes))
    lines = [p.text for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                lines.append(" | ".join(cells))
    return "\n".join(lines)


def extract_text(filename: str, file_bytes: bytes) -> str:
    """Dispatch to the right extractor based on file extension."""
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return extract_text_from_pdf(file_bytes)
    if lower.endswith((".xlsx", ".xlsm")):
        return extract_text_from_xlsx(file_bytes)
    if lower.endswith(".docx"):
        return extract_text_from_docx(file_bytes)
    if lower.endswith((".txt", ".csv", ".md")):
        return file_bytes.decode("utf-8", errors="ignore")
    raise ValueError(f"Unsupported file type: {filename}")


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 150) -> list[str]:
    """Split text into overlapping word-based chunks for retrieval.
    Word-based (not char-based) chunking avoids splitting mid-word and gives
    more consistent chunk semantics across documents.
    """
    words = text.split()
    if not words:
        return []
    chunks = []
    step = max(1, chunk_size - overlap)
    for start in range(0, len(words), step):
        chunk_words = words[start:start + chunk_size]
        if chunk_words:
            chunks.append(" ".join(chunk_words))
        if start + chunk_size >= len(words):
            break
    return chunks
