from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List
import logging
import re

from shared.models import PatientContext
from shared.patient_utils import (
    _calc_age,
    _map_sex,
    _extract_sections,
    _extract_clinical_data,
)
from pipeline.prescription_pipeline import PrescriptionPipeline
from storage.patient_repository import PatientRepository

logger = logging.getLogger("mediguide_server")


@dataclass
class AnalysisResult:
    validated_diseases: list[str]
    recommendations: list[dict[str, Any]]
    report: str | None
    warnings: list[str]
    steps: list[str]


class AnalysisService:
    """Builds patient context from notes and runs the prescription pipeline."""
    def __init__(self, patient_repository: PatientRepository, pipeline_cls: type[PrescriptionPipeline]) -> None:
        self.patient_repository = patient_repository
        self.pipeline_cls = pipeline_cls

    def analyze(self, patient_id: str, note_ids: List[str]) -> AnalysisResult:
        """Analyze selected notes and return validated diseases and recommendations."""
        patient_data = self.patient_repository.load_patient_info(patient_id)

        notes = []
        for note_id in note_ids:
            note = self.patient_repository.load_note_by_id(patient_id, note_id)
            if note:
                notes.append(note)

        if not notes:
            raise ValueError("No note found.")

        symptoms: List[str] = []
        pathologies: List[str] = []
        treatments: List[str] = []
        exams: List[str] = []
        antecedents: List[str] = []
        clinical_items: List[str] = []

        for note in notes:
            filtered_text = note.get("text", "")
            sections = _extract_sections(filtered_text)
            symptoms.extend(sections.get("symptoms", []))
            clinical_items.extend(sections.get("clinical", []))
            pathologies.extend(sections.get("pathologies", []))
            treatments.extend(sections.get("treatments", []))
            exams.extend(sections.get("exams", []))
            antecedents.extend(sections.get("antecedents", []))

        if patient_data.get("medicalHistory"):
            antecedents.extend([s.strip() for s in re.split(r"[,;]", patient_data.get("medicalHistory")) if s.strip()])
        if patient_data.get("currentTreatment"):
            treatments.extend([s.strip() for s in re.split(r"[,;]", patient_data.get("currentTreatment")) if s.strip()])

        clinical_data = _extract_clinical_data(clinical_items)
        age = _calc_age(patient_data.get("dateOfBirth"))
        sex = _map_sex(patient_data.get("gender"))

        patient_context = PatientContext(
            age=age,
            sex=sex,
            symptoms=list(dict.fromkeys(symptoms)),
            antecedents=list(dict.fromkeys(antecedents)),
            current_treatments=list(dict.fromkeys(treatments)),
            clinical_data=clinical_data,
            pathologies=list(dict.fromkeys(pathologies)),
            exams=list(dict.fromkeys(exams)),
        )

        try:
            with self.pipeline_cls() as pipeline:
                result = pipeline.process(
                    patient=patient_context,
                    use_llm_mapping=True,
                    use_vector_search=True,
                )

            formatted_recommendations = []
            seen_compositions = set()

            for rec in result.recommendations:
                comp = rec.substances or []
                if isinstance(comp, list):
                    comp_key = tuple(sorted(s.strip().lower() for s in comp))
                else:
                    comp_key = str(comp).strip().lower()

                if comp_key in seen_compositions:
                    continue

                formatted_recommendations.append({
                    "name": rec.medicine_name,
                    "composition": rec.substances,
                    "side_effects": rec.side_effects,
                    "vidal_warnings": rec.vidal_warnings,
                    "contextual_alerts": rec.warnings,
                    "justification": rec.justification,
                    "posology": rec.dosage or "Voir RCP",
                    "source_url": rec.url,
                })

                seen_compositions.add(comp_key)

            return AnalysisResult(
                validated_diseases=result.validated_diseases,
                recommendations=formatted_recommendations,
                report=result.llm_report,
                warnings=result.global_warnings,
                steps=result.processing_steps,
            )

        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            raise
