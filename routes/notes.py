"""
Note transcription and management routes.
"""
from typing import Optional
import os
from pydantic import BaseModel
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
import logging

from groq import Groq
from shared.paths import DB_ROOT
from ingestion.note_ingestion import NoteIngestionService

logger = logging.getLogger("mediguide_server")

# Import configs
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY environment variable is required")

groq_client = Groq(api_key=GROQ_API_KEY)

router = APIRouter()
note_service = NoteIngestionService(DB_ROOT, groq_client=groq_client)


class TranscribeTextRequest(BaseModel):
    """Payload for creating a note from raw text."""
    patient_id: str
    text_raw: str
    title: Optional[str] = None


class DraftTextRequest(BaseModel):
    """Payload for saving or clearing draft note text."""
    patient_id: str
    session_id: str
    text_raw: str


class NoteSummaryRequest(BaseModel):
    """Payload for generating a note summary."""
    text: str
    timestamp: Optional[str] = None


def _to_http_exception(e: Exception, log_message: Optional[str] = None) -> HTTPException:
    """Map domain exceptions to HTTP exceptions."""
    if isinstance(e, ValueError):
        return HTTPException(status_code=400, detail=str(e))
    if isinstance(e, FileNotFoundError):
        return HTTPException(status_code=404, detail=str(e))
    if log_message:
        logger.error(f"{log_message}: {e}")
    return HTTPException(status_code=500, detail=str(e))


@router.post('/transcribe')
async def transcribe_endpoint(file: UploadFile = File(...), patient_id: str = Form(...)):
    """Transcribe uploaded audio and store the resulting note."""
    try:
        return JSONResponse(status_code=200, content=note_service.transcribe_audio(file, patient_id))
    except Exception as e:
        raise _to_http_exception(e, "Transcribe Error")
    finally: file.file.close()


@router.post('/transcribe_text')
async def transcribe_text_endpoint(payload: TranscribeTextRequest):
    """Create a note from provided text input."""
    try:
        return JSONResponse(status_code=200, content=note_service.transcribe_text(payload.text_raw or "", payload.patient_id, payload.title))
    except Exception as e:
        raise _to_http_exception(e, "Transcribe Text Error")


@router.post('/draft_text')
async def save_draft_text(payload: DraftTextRequest):
    """Save draft text for a patient session."""
    try:
        return JSONResponse(content=note_service.save_draft(payload.patient_id, payload.text_raw or "", payload.session_id))
    except Exception as e:
        raise _to_http_exception(e, "Draft save error")


@router.post('/draft_text/clear')
async def clear_draft_text(payload: DraftTextRequest):
    """Clear draft text for a patient session."""
    try:
        return JSONResponse(content=note_service.clear_draft(payload.patient_id, payload.session_id))
    except Exception as e:
        raise _to_http_exception(e, "Draft clear error")


@router.post("/api/note/summary")
def note_summary(payload: NoteSummaryRequest):
    """Return short summary bullets for note content."""
    try:
        return note_service.note_summary(payload.text, payload.timestamp)
    except Exception as e:
        raise _to_http_exception(e)


@router.delete('/recordings/{item_id}')
async def delete_recording(item_id: str):
    """Delete a note recording by item ID."""
    try:
        return JSONResponse(content=note_service.delete_note_by_item_id(item_id))
    except Exception as e:
        if isinstance(e, FileNotFoundError):
            raise HTTPException(status_code=404, detail="Not found")
        raise _to_http_exception(e)
