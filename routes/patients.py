"""
Patient management routes.
"""
from typing import Optional
import uuid
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import logging

from storage.patient_repository import (
    PatientRepository,
    PatientNotFoundError,
    PatientInfoNotFoundError,
)

logger = logging.getLogger("mediguide_server")

router = APIRouter()
patient_repository = PatientRepository()


class PatientCreate(BaseModel):
    """Payload for patient create and update operations."""
    name: str
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    dateOfBirth: Optional[str] = None
    gender: Optional[str] = None
    visitType: Optional[str] = "consultation"
    phone: Optional[str] = None
    email: Optional[str] = None
    clinicalNote: Optional[str] = None
    allergies: Optional[str] = None
    medicalHistory: Optional[str] = None
    currentTreatment: Optional[str] = None
    referenceNumber: Optional[str] = None


def _build_patient_meta(patient: PatientCreate, folder_id: str) -> dict:
    """Build persisted patient metadata from request payload."""
    return {
        "id": folder_id,
        "name": patient.name,
        "created_at": str(uuid.uuid1()),
        "firstName": patient.firstName,
        "lastName": patient.lastName,
        "dateOfBirth": patient.dateOfBirth,
        "gender": patient.gender,
        "visitType": patient.visitType,
        "phone": patient.phone,
        "email": patient.email,
        "clinicalNote": patient.clinicalNote,
        "allergies": patient.allergies,
        "medicalHistory": patient.medicalHistory,
        "currentTreatment": patient.currentTreatment,
        "referenceNumber": patient.referenceNumber,
    }


def _patient_update_payload(patient: PatientCreate) -> dict:
    """Extract mutable patient fields for update operations."""
    return {
        "visitType": patient.visitType,
        "dateOfBirth": patient.dateOfBirth,
        "phone": patient.phone,
        "email": patient.email,
        "clinicalNote": patient.clinicalNote,
        "allergies": patient.allergies,
        "medicalHistory": patient.medicalHistory,
        "currentTreatment": patient.currentTreatment,
        "referenceNumber": patient.referenceNumber,
    }


@router.get('/patients')
async def list_patients():
    """List all patients."""
    try:
        return patient_repository.list_patients()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post('/patients')
async def create_patient(patient: PatientCreate):
    """Create a patient and initialize storage folder."""
    safe_name = "".join([c for c in patient.name if c.isalnum() or c in (' ', '_', '-')]).strip() or "Patient_X"
    folder_id = f"{safe_name.replace(' ', '_')}_{uuid.uuid4().hex[:8]}"
    meta = _build_patient_meta(patient, folder_id)
    try:
        return JSONResponse(content=patient_repository.create_patient(folder_id, meta))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/patients/{patient_id}/history')
async def get_patient_history(patient_id: str):
    """Return all notes for a patient."""
    try:
        return patient_repository.load_patient_notes(patient_id)
    except PatientNotFoundError:
        raise HTTPException(status_code=404, detail="Patient introuvable")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/patients/{patient_id}/info')
async def get_patient_info(patient_id: str):
    """Return complete patient information."""
    try:
        return patient_repository.load_patient_info(patient_id)
    except PatientInfoNotFoundError:
        raise HTTPException(status_code=404, detail="Patient introuvable")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put('/patients/{patient_id}')
async def update_patient(patient_id: str, patient: PatientCreate):
    """Update patient information in local storage and Qdrant."""
    updates = _patient_update_payload(patient)
    try:
        return JSONResponse(content=patient_repository.update_patient_info(patient_id, updates))
    except PatientInfoNotFoundError:
        raise HTTPException(status_code=404, detail="Patient introuvable")
    except Exception as e:
        logger.error(f"Patient update error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete('/patients/{patient_id}')
async def delete_patient(patient_id: str):
    """Delete a patient and all related local and vector records."""
    try:
        patient_repository.delete_patient(patient_id)
        return JSONResponse(content={"status": "deleted", "id": patient_id})
    except PatientNotFoundError:
        raise HTTPException(status_code=404, detail="Patient introuvable")
    except Exception as e:
        logger.error(f"Patient delete error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
