"""
Medication Recommender for the Medical Prescription System.
Generates medication recommendations with justifications and warnings.
"""

from typing import Optional

from shared.config import Config
from shared.models import MedicationRecommendation, PatientContext
from storage.neo4j_client import Neo4jClient
from shared.logger import logger


class MedicationRecommender:
    """
    Recommends medications based on patient context and validated diseases.
    Provides justifications from the knowledge graph and generates contextual warnings.
    """
    
    def __init__(self, config: Optional[Config] = None, neo4j_client: Optional[Neo4jClient] = None):
        """
        Initialize the medication recommender.
        
        Args:
            config: Configuration object
            neo4j_client: Optional existing Neo4j client to reuse
        """
        self.config = config or Config.get_instance()
        self._neo4j_client = neo4j_client
        self._owns_client = neo4j_client is None
    
    @property
    def neo4j(self) -> Neo4jClient:
        """Lazy initialization of Neo4j client"""
        if self._neo4j_client is None:
            self._neo4j_client = Neo4jClient(self.config)
        return self._neo4j_client
    
    def close(self):
        """Close resources if we own them"""
        if self._owns_client and self._neo4j_client:
            self._neo4j_client.close()
    
    def recommend(
        self, 
        patient: PatientContext, 
        validated_diseases: list[str],
        max_per_disease: int = 5
    ) -> list[MedicationRecommendation]:
        """
        Generate medication recommendations for the patient.
        
        Args:
            patient: Patient context
            validated_diseases: List of validated disease names
            max_per_disease: Maximum recommendations per disease
            
        Returns:
            List of MedicationRecommendation objects
        """
        recommendations = []
        seen_medicines = set()  # Avoid duplicates
        
        # Collect patient conditions for warning checks
        patient_conditions = (
            patient.antecedents + 
            patient.pathologies + 
            patient.current_treatments
        )
        
        for disease in validated_diseases:
            # Find medicines that treat this disease
            medicines = self.neo4j.find_medicines_for_condition(disease, limit=max_per_disease * 2)
            logger.info(f"Found {len(medicines)} potential medicines for disease: {disease}")
            
            count = 0
            for med in medicines:
                if med["name"] in seen_medicines:
                    continue
                if count >= max_per_disease:
                    break
                    
                seen_medicines.add(med["name"])
                
                # Get full medicine details
                details = self.neo4j.get_medicine_details(med["name"])
                
                if not details:
                    continue
                
                # Check for patient-specific warnings
                patient_warnings = self.neo4j.check_patient_contraindications(
                    med["name"], 
                    patient_conditions
                )
                
                # Generate evidence for interpretability
                evidence = self.neo4j.get_evidence_subgraph(
                    med["name"],
                    patient_conditions,
                    [disease]
                )
                
                # Build recommendation
                recommendation = MedicationRecommendation(
                    medicine_name=med["name"],
                    justification=self._build_justification(disease, details),
                    treats=details.get("treats", []),
                    warnings=self._professionalize_warnings(patient_warnings + details.get("warnings", [])[:5]),
                    contraindications=details.get("contraindications", []),
                    interactions=details.get("interactions", []),
                    dosage=details.get("dosage_general"),
                    dosage_adult=details.get("dosage_adult"),
                    dosage_child=details.get("dosage_child"),
                    dosage_elderly=details.get("dosage_elderly"),
                    frequency=details.get("frequency"),
                    url=details.get("url"),
                    substances=details.get("substances", []),
                    side_effects=details.get("side_effects", [])[:5],
                    vidal_warnings=details.get("warnings", [])[:5],
                    pregnancy_info=details.get("pregnancy_info"),
                    breastfeeding_info=details.get("breastfeeding_info"),
                    evidence_query=evidence.get("query"),
                    evidence_data=evidence
                )
                
                recommendations.append(recommendation)
                count += 1
        
        # Sort by number of warnings (fewer warnings = better candidate)
        recommendations.sort(key=lambda r: len(r.warnings))
        
        return recommendations

    def _professionalize_warnings(self, warnings: list[str]) -> list[str]:
        """
        Uses LLM to filter and rewrite warnings for healthcare professionals.
        Removes patient-facing advice and extracts clinical facts.
        """
        if not warnings:
            return []
            
        # If no LLM client is available, return original warnings 
        # (better than brittle hardcoded filtering)
        if not self.config.edenai.api_key:
            return warnings

        try:
            # We need an LLM client here. If not passed in init, create a temporary one or import it.
            # ideally, we should use self._llm_client if we had one injected.
            # For now, we'll instantiate one on demand if needed, but it's better to inject it.
            # But wait, looking at the imports, we don't have EdenAIClient imported in this file yet.
            # We should probably return the raw warnings here and let a higher level service handle it,
            # OR we import it inside the method to avoid circular deps if any.
            
            from integrations.edenai_client import EdenAIClient
            client = EdenAIClient(self.config)
            
            prompt = f"""
            You are a clinical pharmacist assistant. 
            Rewrite the following list of medicine warnings to be concise and targeted at a DOCTOR.
            
            Rules:
            1. Remove all patient-facing advice (e.g. "ask your pharmacist", "keep out of reach of children").
            2. Keep only clinical facts (contraindications, specific risks, monitoring required).
            3. If a warning is purely "don't take without advice", remove it.
            4. Merge duplicates.
            5. Return a JSON list of strings.
            
            Input Warnings:
            {warnings}
            """
            
            response = client.call_llm(prompt)
            if isinstance(response, list):
                return [w for w in response if isinstance(w, str)]
            return warnings # Fallback if response is weird
            
        except Exception as e:
            # Fallback to original warnings on error
            print(f"Warning optimization failed: {e}")
            return warnings
    
    def _build_justification(self, disease: str, medicine_details: dict) -> str:
        """
        Build a justification string for why this medicine is recommended.
        
        Args:
            disease: The disease being treated
            medicine_details: Full medicine details from DB
            
        Returns:
            Justification string
        """
        parts = []
        
        name = medicine_details.get("name", "This medicine")
        parts.append(f"{name} is indicated for treating: {disease}.")
        
        # Add substance info if available
        substances = medicine_details.get("substances", [])
        if substances:
            parts.append(f"Contains: {', '.join(substances[:3])}.")
        
        # Add drug class info
        classes = medicine_details.get("drug_classes", [])
        if classes:
            parts.append(f"Therapeutic class: {', '.join(classes[:2])}.")
        
        return " ".join(parts)
    
    def get_global_warnings(self, patient: PatientContext) -> list[str]:
        """
        Generate global warnings based on patient context.
        These are not tied to specific medications.
        
        Args:
            patient: Patient context
            
        Returns:
            List of warning messages
        """
        warnings = []
        
        # Age-related warnings
        if patient.age:
            if patient.age < 18:
                warnings.append("⚠️ Pediatric patient: verify child-appropriate dosing.")
            elif patient.age >= 65:
                warnings.append("⚠️ Older adult patient: consider dose adjustment and monitor renal function.")
        
        # Pregnancy warnings
        if patient.sex == "F" and patient.age and 15 <= patient.age <= 50:
            # Reproductive age - check for pregnancy-related antecedents
            pregnancy_terms = ["enceinte", "grossesse", "gestante"]
            for ant in patient.antecedents + patient.pathologies:
                if any(term in ant.lower() for term in pregnancy_terms):
                    warnings.append("⚠️ Pregnancy: verify compatibility of all prescribed medications.")
                    break
        
        # Drug interaction warning if multiple treatments
        if len(patient.current_treatments) > 2:
            warnings.append(f"⚠️ Polypharmacy ({len(patient.current_treatments)} treatments): verify drug interactions.")
        
        # Check for known high-risk conditions
        high_risk_conditions = {
            "diabète": "Monitor blood glucose with any new treatment.",
            "insuffisance rénale": "Adjust dosing based on renal clearance.",
            "insuffisance hépatique": "Avoid hepatotoxic medications.",
            "allergie": "Verify absence of allergens in prescribed medications."
        }
        
        for condition, warning in high_risk_conditions.items():
            for ant in patient.antecedents + patient.pathologies:
                if condition in ant.lower():
                    warnings.append(f"⚠️ {condition.capitalize()}: {warning}")
                    break
        
        return warnings
