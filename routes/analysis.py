"""
RAG analysis and prescription reasoning routes.
"""
from typing import List
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import logging

from pipeline.prescription_pipeline import PrescriptionPipeline
from pipeline.analysis_service import AnalysisService
from storage.patient_repository import (
    PatientRepository,
    PatientNotFoundError,
    PatientInfoNotFoundError,
)

logger = logging.getLogger("mediguide_server")

router = APIRouter()


class RagRequest(BaseModel):
    """Request payload for note-based RAG analysis."""
    patient_id: str
    note_ids: List[str]  # IDs of selected notes


@router.post('/rag/analyze')
async def analyze_notes(request: RagRequest):
    """Run analysis pipeline on selected patient notes."""
    logger.info(f"Analysis requested for {len(request.note_ids)} notes.")
    try:
        service = AnalysisService(PatientRepository(), PrescriptionPipeline)
        result = service.analyze(request.patient_id, request.note_ids)
        return JSONResponse(
            content={
                "status": "success",
                "data": {
                    "validated_diseases": result.validated_diseases,
                    "recommendations": result.recommendations,
                    "medical_report": result.report,
                    "processing_steps": result.steps,
                    "global_warnings": result.warnings,
                },
            },
            status_code=200,
        )
    except PatientNotFoundError: raise HTTPException(status_code=404, detail="Patient introuvable")
    except PatientInfoNotFoundError: raise HTTPException(status_code=404, detail="Infos patient manquantes")
    except ValueError as e:
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=400)
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)
