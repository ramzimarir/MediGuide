"""
Data models for the Medical Prescription System.
Defines dataclasses for patient context, medications, and recommendations.
"""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class PatientContext:
    """
    Represents the patient's clinical context.
    All fields are optional to handle incomplete data.
    """
    # Demographics
    age: Optional[int] = None
    sex: Optional[str] = None  # 'M', 'F', or None
    
    # Medical history
    antecedents: list[str] = field(default_factory=list)
    
    # Current presentation
    symptoms: list[str] = field(default_factory=list)
    motifs: list[str] = field(default_factory=list)  # Reasons for consultation
    
    # Clinical measurements
    clinical_data: dict[str, Any] = field(default_factory=dict)
    # Example: {"TA": "14/9", "Sat": "98%", "Temperature": "38.5°C"}
    
    # Diagnoses
    pathologies: list[str] = field(default_factory=list)
    
    # Current medications
    current_treatments: list[str] = field(default_factory=list)
    
    # Exams and procedures
    exams: list[str] = field(default_factory=list)
    
    def to_prompt_text(self) -> str:
        """Convert patient context to readable text for LLM prompts"""
        sections = []
        
        if self.age or self.sex:
            demo = []
            if self.age:
                demo.append(f"Âge: {self.age} ans")
            if self.sex:
                demo.append(f"Sexe: {self.sex}")
            sections.append("CONTEXTE PATIENT: " + ", ".join(demo))
        
        if self.antecedents:
            sections.append("ANTÉCÉDENTS: " + ", ".join(self.antecedents))
        
        if self.symptoms or self.motifs:
            items = self.symptoms + self.motifs
            sections.append("SYMPTÔMES & MOTIFS: " + ", ".join(items))
        
        if self.clinical_data:
            data = ", ".join(f"{k}: {v}" for k, v in self.clinical_data.items())
            sections.append("DONNÉES CLINIQUES: " + data)
        
        if self.pathologies:
            sections.append("PATHOLOGIES: " + ", ".join(self.pathologies))
        
        if self.current_treatments:
            sections.append("TRAITEMENTS ACTUELS: " + ", ".join(self.current_treatments))
        
        if self.exams:
            sections.append("EXAMENS: " + ", ".join(self.exams))
        
        return "\n".join(sections)


@dataclass
class OntologyEntity:
    """
    Represents an entity mapped to the ontology.
    Used for linking patient data to graph database concepts.
    """
    entity_type: str  # 'Condition', 'Symptom', 'Medicine', 'Substance', etc.
    name: str  # Normalized name
    original_text: str  # Original text from patient context
    confidence: float = 1.0  # Confidence score from LLM


@dataclass 
class MedicationRecommendation:
    """
    A medication recommendation with justification and warnings.
    """
    medicine_name: str
    justification: str  # Why this medication is recommended
    treats: list[str] = field(default_factory=list)  # Conditions it treats
    warnings: list[str] = field(default_factory=list)  # Context-specific warnings
    contraindications: list[str] = field(default_factory=list)
    interactions: list[str] = field(default_factory=list)  # Drug interactions
    dosage: Optional[str] = None
    dosage_adult: Optional[str] = None
    dosage_child: Optional[str] = None
    dosage_elderly: Optional[str] = None
    frequency: Optional[str] = None
    url: Optional[str] = None
    substances: list[str] = field(default_factory=list)
    side_effects: list[str] = field(default_factory=list)
    vidal_warnings: list[str] = field(default_factory=list)
    pregnancy_info: Optional[str] = None
    breastfeeding_info: Optional[str] = None
    confidence_score: float = 1.0
    
    # Interpretability fields
    evidence_query: Optional[str] = None  # Cypher query to see evidence in Neo4j
    evidence_data: Optional[dict] = None  # Subgraph data (nodes/edges)


@dataclass
class PrescriptionResult:
    """
    Complete result from the prescription pipeline.
    """
    patient: PatientContext
    validated_diseases: list[str]  # Diseases validated against graph
    unvalidated_diseases: list[str]  # Diseases not found in graph
    recommendations: list[MedicationRecommendation]
    global_warnings: list[str] = field(default_factory=list)  # Patient-level warnings
    processing_steps: list[str] = field(default_factory=list)  # For debugging/transparency
    
    # Global interpretability
    summary_query: Optional[str] = None  # Cypher query to see all patient-related nodes
    llm_report: Optional[str] = None  # Generated report text
