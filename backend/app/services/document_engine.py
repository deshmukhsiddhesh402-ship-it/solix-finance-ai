"""
Module 7: AI Chat / RAG — document ingestion.

Extracts text from uploaded PDFs, Excel files, and plain text, then splits
it into overlapping chunks suitable for retrieval. Kept dependency-light:
pypdf for PDFs, openpyxl for Excel (both already in requirements.txt).
"""
import io
from openpyxl import load_workbook


MAX_DOCUMENT_SHEETS = 50
MAX_DOCUMENT_ROWS_PER_SHEET = 100_000
MAX_DOCUMENT_COLUMNS_PER_SHEET = 200
MAX_DOCUMENT_TABLES = 100
MAX_DOCUMENT_EXTRACTED_CHARS = 5_000_000
MAX_DOCUMENT_CHUNKS = 10_000


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract plain text from a PDF's pages."""
    from pypdf import PdfReader  # local import: optional dependency, only needed here
    reader = PdfReader(io.BytesIO(file_bytes))
    if len(reader.pages) > 50:
        raise ValueError("PDF exceeds the 50-page document extraction limit.")
    pages = []
    total_chars = 0
    for page in reader.pages:
        page_text = page.extract_text() or ""
        total_chars += len(page_text)
        if total_chars > MAX_DOCUMENT_EXTRACTED_CHARS:
            raise ValueError("Document text exceeds the supported extraction limit.")
        pages.append(page_text)
    return "\n".join(pages)


def extract_text_from_xlsx(file_bytes: bytes) -> str:
    """Flatten workbook cells into readable text with parser resource bounds."""
    wb = load_workbook(io.BytesIO(file_bytes), data_only=True, read_only=True)
    try:
        if len(wb.worksheets) > MAX_DOCUMENT_SHEETS:
            raise ValueError("Workbook exceeds the supported sheet limit.")
        lines = []
        total_chars = 0
        for sheet in wb.worksheets:
            if sheet.max_row > MAX_DOCUMENT_ROWS_PER_SHEET:
                raise ValueError("Worksheet exceeds the supported row limit.")
            if sheet.max_column > MAX_DOCUMENT_COLUMNS_PER_SHEET:
                raise ValueError("Worksheet exceeds the supported column limit.")
            lines.append(f"--- Sheet: {sheet.title} ---")
            for row in sheet.iter_rows(
                values_only=True,
                max_row=MAX_DOCUMENT_ROWS_PER_SHEET,
                max_col=MAX_DOCUMENT_COLUMNS_PER_SHEET,
            ):
                cells = [str(c) for c in row if c is not None]
                if cells:
                    line = " | ".join(cells)
                    total_chars += len(line) + 1
                    if total_chars > MAX_DOCUMENT_EXTRACTED_CHARS:
                        raise ValueError("Document text exceeds the supported extraction limit.")
                    lines.append(line)
        return "\n".join(lines)
    finally:
        wb.close()


def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extract paragraph and table text with parser resource bounds."""
    from docx import Document  # local import: optional dependency, only needed here
    doc = Document(io.BytesIO(file_bytes))
    lines = []
    total_chars = 0
    for paragraph in doc.paragraphs:
        text = paragraph.text.strip()
        if text:
            total_chars += len(text) + 1
            if total_chars > MAX_DOCUMENT_EXTRACTED_CHARS:
                raise ValueError("Document text exceeds the supported extraction limit.")
            lines.append(text)
    if len(doc.tables) > MAX_DOCUMENT_TABLES:
        raise ValueError("Document exceeds the supported table limit.")
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                line = " | ".join(cells)
                total_chars += len(line) + 1
                if total_chars > MAX_DOCUMENT_EXTRACTED_CHARS:
                    raise ValueError("Document text exceeds the supported extraction limit.")
                lines.append(line)
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
        text = file_bytes.decode("utf-8", errors="ignore")
        if len(text) > MAX_DOCUMENT_EXTRACTED_CHARS:
            raise ValueError("Document text exceeds the supported extraction limit.")
        return text
    raise ValueError(f"Unsupported file type: {filename}")


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 150) -> list[str]:
    """Split text into overlapping word-based chunks for retrieval.
    Word-based (not char-based) chunking avoids splitting mid-word and gives
    more consistent chunk semantics across documents.
    """
    if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("chunk_size must be positive and overlap must be between 0 and chunk_size - 1.")
    words = text.split()
    if not words:
        return []
    chunks = []
    step = chunk_size - overlap
    for start in range(0, len(words), step):
        chunk_words = words[start:start + chunk_size]
        if chunk_words:
            if len(chunks) >= MAX_DOCUMENT_CHUNKS:
                raise ValueError("Document produces too many retrieval chunks.")
            chunks.append(" ".join(chunk_words))
        if start + chunk_size >= len(words):
            break
    return chunks
