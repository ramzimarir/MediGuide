"""
Ontology Mapper for the Medical Prescription System.
Uses LLM to transform patient context into ontology-compatible entities.
"""

from typing import Optional

from shared.config import Config
from integrations.edenai_client import EdenAIClient
from shared.models import OntologyEntity, PatientContext


class OntologyMapper:
    """
    Maps patient data to ontology entities using LLM.
    Transforms free-text clinical data into normalized concepts.
    """
    
    SYSTEM_PROMPT = """Tu es un assistant médical expert en ontologies médicales.
Ta tâche est de normaliser les données patient en entités d'ontologie standardisées.

Types d'entités à extraire:
- Condition: Maladies, pathologies, diagnostics
- Symptom: Symptômes présentés par le patient
- Antecedent: Antécédents médicaux du patient
- Treatment: Médicaments ou traitements actuels
- Substance: Substances actives des médicaments

IMPORTANT:
- Normalise les noms en français médical standard
- Utilise des termes génériques quand possible (ex: "diabète de type 2" → "diabète type 2")
- Supprime les articles et déterminants
- Garde les termes médicaux précis"""

    EXTRACTION_PROMPT_TEMPLATE = """Analyse les données patient suivantes et extrais les entités médicales normalisées.

DONNÉES PATIENT:
{patient_text}

MALADIES CANDIDATES (de la base vectorielle):
{diseases}

Réponds en JSON avec le format suivant:
{{
    "conditions": [
        {{"name": "nom normalisé", "original": "texte original", "confidence": 0.95}}
    ],
    "symptoms": [
        {{"name": "nom normalisé", "original": "texte original", "confidence": 0.9}}
    ],
    "antecedents": [
        {{"name": "nom normalisé", "original": "texte original", "confidence": 0.85}}
    ],
    "treatments": [
        {{"name": "nom normalisé", "original": "texte original", "confidence": 0.9}}
    ]
}}

Extrais TOUTES les entités pertinentes. Inclus seulement les entités réellement présentes dans les données."""
    
    def __init__(self, config: Optional[Config] = None):
        """
        Initialize the ontology mapper.
        
        Args:
            config: Configuration object
        """
        self.config = config or Config.get_instance()
        self.llm_client = EdenAIClient(self.config)
    
    def map_patient_to_ontology(
        self, 
        patient: PatientContext,
        candidate_diseases: list[str] = None
    ) -> dict[str, list[OntologyEntity]]:
        """
        Map patient context to ontology entities.
        
        Args:
            patient: Patient context data
            candidate_diseases: Optional list of diseases from vector DB
            
        Returns:
            Dictionary with entity types as keys and lists of OntologyEntity
        """
        # Build prompt
        patient_text = patient.to_prompt_text()
        diseases_text = ", ".join(candidate_diseases) if candidate_diseases else "Aucune"
        
        prompt = self.EXTRACTION_PROMPT_TEMPLATE.format(
            patient_text=patient_text,
            diseases=diseases_text
        )
        
        # Call LLM
        try:
            response = self.llm_client.call_llm_json(prompt, self.SYSTEM_PROMPT)
        except Exception as e:
            # Return empty on failure
            print(f"Warning: LLM call failed: {e}")
            return {
                "conditions": [],
                "symptoms": [],
                "antecedents": [],
                "treatments": []
            }
        
        # Parse response into OntologyEntity objects
        result = {}
        for entity_type in ["conditions", "symptoms", "antecedents", "treatments"]:
            entities = []
            for item in response.get(entity_type, []):
                entities.append(OntologyEntity(
                    entity_type=entity_type.rstrip('s').capitalize(),  # conditions -> Condition
                    name=item.get("name", ""),
                    original_text=item.get("original", ""),
                    confidence=item.get("confidence", 1.0)
                ))
            result[entity_type] = entities
        
        return result
    
    def normalize_condition(self, condition: str) -> str:
        """
        Normalize a single condition name using LLM.
        
        Args:
            condition: Raw condition text
            
        Returns:
            Normalized condition name
        """
        prompt = f"""Normalise ce terme médical en français standard.
Retourne UNIQUEMENT le terme normalisé, sans explication.

Terme: {condition}

Terme normalisé:"""
        
        try:
            response = self.llm_client.call_llm(prompt, temperature=0.1, max_tokens=100)
            return response.strip().strip('"').strip("'")
        except Exception:
            return condition  # Return original on failure
