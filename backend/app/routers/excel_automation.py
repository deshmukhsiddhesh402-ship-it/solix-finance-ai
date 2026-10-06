"""
Module 8: Excel Automation — API layer over excel_automation_engine.py

SESSION STORAGE NOTE: same pattern as the AI Chat module — cleaned
DataFrames are kept in-memory keyed by session_id for the download step.
Fine for a single-user demo; production should use Redis or object storage
(S3/GCS) for the intermediate file instead.
"""
import io
import uuid
import zipfile
import pandas as pd
from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.routers.enterprise import require_permission
from app.services.excel_automation_engine import (
    clean_dataframe, remove_duplicates, detect_errors, auto_categorize_expenses,
)

router = APIRouter()
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_ROWS = 100_000
MAX_COLUMNS = 200
MAX_EXCEL_ZIP_ENTRIES = 200
MAX_EXCEL_UNCOMPRESSED_BYTES = 50 * 1024 * 1024

_CLEANED_FILES: dict[str, dict] = {}


def _get_cleaned_session(session_id: str, org_id: str, user_id: str) -> dict:
    try:
        session_uuid = uuid.UUID(str(session_id))
        org_uuid = uuid.UUID(str(org_id))
        user_uuid = uuid.UUID(str(user_id))
    except (ValueError, AttributeError, TypeError) as exc:
        raise HTTPException(400, detail="Invalid session or organization identifier.") from exc
    session = _CLEANED_FILES.get(str(session_uuid))
    if session is None:
        raise HTTPException(404, detail="Session not found or expired. Re-upload the file.")
    if session["org_id"] != str(org_uuid):
        raise HTTPException(403, detail="Cleaned file session does not belong to this organization.")
    if session["user_id"] != str(user_uuid):
        raise HTTPException(403, detail="Cleaned file session does not belong to this user.")
    return session


def _validate_excel_archive(file_bytes: bytes) -> None:
    """Reject ZIP-based spreadsheets with excessive archive expansion/entries."""
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_EXCEL_ZIP_ENTRIES:
                raise HTTPException(413, detail="Spreadsheet contains too many archive entries.")
            total_uncompressed = sum(max(0, info.file_size) for info in infos)
            if total_uncompressed > MAX_EXCEL_UNCOMPRESSED_BYTES:
                raise HTTPException(413, detail="Spreadsheet expands beyond the supported size limit.")
    except zipfile.BadZipFile as exc:
        raise HTTPException(400, detail="Invalid XLSX/XLSM archive.") from exc


def _validate_dataframe_shape(df: pd.DataFrame) -> pd.DataFrame:
    if len(df.index) > MAX_ROWS:
        raise HTTPException(413, detail=f"Spreadsheet exceeds the {MAX_ROWS:,}-row limit.")
    if len(df.columns) > MAX_COLUMNS:
        raise HTTPException(413, detail=f"Spreadsheet exceeds the {MAX_COLUMNS}-column limit.")
    return df


def _read_upload_to_df(filename: str, file_bytes: bytes) -> pd.DataFrame:
    lower = filename.lower()
    if lower.endswith(".csv"):
        df = pd.read_csv(io.BytesIO(file_bytes), nrows=MAX_ROWS + 1)
    elif lower.endswith((".xlsx", ".xlsm")):
        _validate_excel_archive(file_bytes)
        df = pd.read_excel(io.BytesIO(file_bytes))
    else:
        raise HTTPException(400, detail="Only .csv, .xlsx, and .xlsm files are supported.")
    return _validate_dataframe_shape(df)


@router.post("/auto-clean")
async def auto_clean(
    file: UploadFile = File(...),
    dedupe: bool = Form(True),
    categorize_column: str | None = Form(None),
    org_id: str = Query(...),
    user_id: str = Depends(require_permission("reports", "create")),
):
    """Run the full pipeline: clean -> dedupe -> detect errors -> (optional) categorize.
    Returns a JSON summary + preview rows, plus a session_id to download the cleaned file.
    """
    try:
        org_uuid = uuid.UUID(str(org_id))
        user_uuid = uuid.UUID(str(user_id))
    except (ValueError, AttributeError, TypeError) as exc:
        raise HTTPException(400, detail="Invalid organization or user identifier.") from exc
    file_bytes = await file.read()
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, detail="Uploaded spreadsheet exceeds the 10 MB limit.")
    df = _read_upload_to_df(file.filename or "", file_bytes)

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
    _CLEANED_FILES[session_id] = {"df": cleaned, "org_id": str(org_uuid), "user_id": str(user_uuid)}

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
def download_cleaned_file(session_id: str, org_id: str = Query(...), _user: str = Depends(require_permission("reports", "view"))):
    session = _get_cleaned_session(session_id, org_id, _user)
    df = session["df"]
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
def merge_cleaned_sessions(req: MergeRequest, org_id: str = Query(...), user_id: str = Depends(require_permission("reports", "create"))):
    """Merge previously-cleaned sessions (by concatenation) into one dataset."""
    dfs = []
    try:
        org_uuid = uuid.UUID(str(org_id))
        user_uuid = uuid.UUID(str(user_id))
    except (ValueError, AttributeError, TypeError) as exc:
        raise HTTPException(400, detail="Invalid organization or user identifier.") from exc
    for sid in req.session_ids:
        try:
            session_uuid = uuid.UUID(str(sid))
        except (ValueError, AttributeError, TypeError) as exc:
            raise HTTPException(400, detail="Invalid cleaned-file session identifier.") from exc
        session = _CLEANED_FILES.get(str(session_uuid))
        if session is None:
            raise HTTPException(404, detail=f"Session {sid} not found.")
        if session["org_id"] != str(org_uuid):
            raise HTTPException(403, detail=f"Session {sid} does not belong to this organization.")
        if session["user_id"] != str(user_uuid):
            raise HTTPException(403, detail=f"Session {sid} does not belong to this user.")
        dfs.append(session["df"])
    if not dfs:
        raise HTTPException(422, detail="No valid sessions provided.")

    merged = pd.concat(dfs, ignore_index=True, sort=False)
    session_id = str(uuid.uuid4())
    _CLEANED_FILES[session_id] = {"df": merged, "org_id": str(org_uuid), "user_id": str(user_uuid)}
    return {
        "session_id": session_id,
        "row_count": len(merged),
        "columns": list(merged.columns),
        "preview": merged.head(10).fillna("").to_dict(orient="records"),
    }
