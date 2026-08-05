"""
Module 8: Excel Automation — API layer over excel_automation_engine.py

SESSION STORAGE NOTE: same pattern as the AI Chat module — cleaned
DataFrames are kept in-memory keyed by session_id for the download step.
Fine for a single-user demo; production should use Redis or object storage
(S3/GCS) for the intermediate file instead.
"""
import io
import uuid
import pandas as pd
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.services.excel_automation_engine import (
    clean_dataframe, remove_duplicates, detect_errors, auto_categorize_expenses,
)

router = APIRouter()

_CLEANED_FILES: dict[str, pd.DataFrame] = {}


def _read_upload_to_df(filename: str, file_bytes: bytes) -> pd.DataFrame:
    lower = filename.lower()
    if lower.endswith(".csv"):
        return pd.read_csv(io.BytesIO(file_bytes))
    if lower.endswith((".xlsx", ".xlsm")):
        return pd.read_excel(io.BytesIO(file_bytes))
    raise HTTPException(400, detail="Only .csv, .xlsx, and .xlsm files are supported.")


@router.post("/auto-clean")
async def auto_clean(
    file: UploadFile = File(...),
    dedupe: bool = Form(True),
    categorize_column: str | None = Form(None),
):
    """Run the full pipeline: clean -> dedupe -> detect errors -> (optional) categorize.
    Returns a JSON summary + preview rows, plus a session_id to download the cleaned file.
    """
    file_bytes = await file.read()
    df = _read_upload_to_df(file.filename, file_bytes)

    cleaned, clean_report = clean_dataframe(df)

    dedupe_removed = 0
    if dedupe:
        cleaned, dedupe_removed = remove_duplicates(cleaned)

    errors = detect_errors(cleaned)

    if categorize_column:
        try:
            cleaned = auto_categorize_expenses(cleaned, categorize_column)
        except ValueError as e:
            raise HTTPException(422, detail=str(e))

    session_id = str(uuid.uuid4())
    _CLEANED_FILES[session_id] = cleaned

    preview = cleaned.head(10).fillna("").to_dict(orient="records")

    return {
        "session_id": session_id,
        "clean_report": clean_report,
        "duplicates_removed": dedupe_removed,
        "errors_detected": errors,
        "row_count": len(cleaned),
        "columns": list(cleaned.columns),
        "preview": preview,
    }


@router.get("/download/{session_id}")
def download_cleaned_file(session_id: str):
    df = _CLEANED_FILES.get(session_id)
    if df is None:
        raise HTTPException(404, detail="Session not found or expired. Re-upload the file.")

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Cleaned Data")
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=solix_cleaned_data.xlsx"},
    )


class MergeRequest(BaseModel):
    session_ids: list[str]


@router.post("/merge")
def merge_cleaned_sessions(req: MergeRequest):
    """Merge previously-cleaned sessions (by concatenation) into one dataset."""
    dfs = []
    for sid in req.session_ids:
        df = _CLEANED_FILES.get(sid)
        if df is None:
            raise HTTPException(404, detail=f"Session {sid} not found.")
        dfs.append(df)
    if not dfs:
        raise HTTPException(422, detail="No valid sessions provided.")

    merged = pd.concat(dfs, ignore_index=True, sort=False)
    session_id = str(uuid.uuid4())
    _CLEANED_FILES[session_id] = merged
    return {
        "session_id": session_id,
        "row_count": len(merged),
        "columns": list(merged.columns),
        "preview": merged.head(10).fillna("").to_dict(orient="records"),
    }
