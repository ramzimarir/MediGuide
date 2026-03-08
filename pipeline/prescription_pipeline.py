"""
Prescription Pipeline for the Medical Prescription System.
Orchestrates the complete workflow from patient data to recommendations.
"""

from typing import Optional, List

from shared.config import Config
from shared.logger import logger
from pipeline.disease_validator import DiseaseValidator
from pipeline.medication_recommender import MedicationRecommender
from pipeline.vector_search import VectorSearchService
from pipeline.hybrid_retriever import HybridRetriever
from shared.models import PatientContext, PrescriptionResult
from storage.neo4j_client import Neo4jClient
from pipeline.ontology_mapper import OntologyMapper
from integrations.edenai_client import EdenAIClient


class PrescriptionPipeline:
    """
    Main pipeline that orchestrates the complete prescription workflow:
    1. (Optional) Parse patient data with LLM
    2. (Optional) Find candidate diseases matches via Vector Search
    3. Validate diseases against graph
    4. Generate medication recommendations
    5. Compile warnings and justifications
    """
    
    def __init__(self, config: Optional[Config] = None):
        """
        Initialize the prescription pipeline.
        
        Args:
            config: Configuration object. If None, uses singleton instance.
        """
        self.config = config or Config.get_instance()
        
        # Initialize core components
        self.neo4j_client = Neo4jClient(self.config)
        self.disease_validator = DiseaseValidator(self.config, self.neo4j_client)
        self.medication_recommender = MedicationRecommender(self.config, self.neo4j_client)
        
        # Initialize components (lazy loaded)
        self.ontology_mapper: Optional[OntologyMapper] = None
        self.vector_search: Optional[VectorSearchService] = VectorSearchService(
            url=getattr(self.config, "QDRANT_URL", "http://localhost:6333")
        )
        self.hybrid_retriever = HybridRetriever(
            self.neo4j_client,
            self.vector_search,
            self.disease_validator,
        )
    
    def _get_vector_search(self) -> VectorSearchService:
        if not self.vector_search:
            self.vector_search = VectorSearchService(url=getattr(self.config, "QDRANT_URL", "http://localhost:6333"))
        return self.vector_search

    def _get_mapper(self) -> OntologyMapper:
        if not self.ontology_mapper:
            self.ontology_mapper = OntologyMapper(self.config)
        return self.ontology_mapper
        
    def close(self):
        """Close all resources"""
        if self.neo4j_client:
            self.neo4j_client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def process(
        self, 
        patient: PatientContext, 
        candidate_diseases: Optional[List[str]] = None,
        use_llm_mapping: bool = True,
        use_vector_search: bool = True
    ) -> PrescriptionResult:
        """
        Process a patient case and generate recommendations.
        
        Args:
            patient: Patient context data
            candidate_diseases: Optional diseases from list. If None, uses vector search.
            use_llm_mapping: Whether to use LLM for ontology mapping
            use_vector_search: Whether to use Qdrant to find diseases if candidates not provided
            
        Returns:
            PrescriptionResult with recommendations and warnings
        """
        logger.info(f"Starting pipeline execution for patient: age={patient.age}, sex={patient.sex}")
        steps = []
        
        # Step 1: Map patient to ontology (optional LLM step)
        if use_llm_mapping:
            steps.append("1. Normalisation des données patient (LLM)")
            mapper = self._get_mapper()
            logger.info("Step 1: Mapped patient to ontology (using LLM)")
            
            # Let's stick to the previous logic for LLM mapping to avoid breaking:
            ontology_entities = mapper.map_patient_to_ontology(patient, candidate_diseases)
            mapped_conditions = [e.name for e in ontology_entities.get("conditions", [])]
            logger.info(f"Extracted {len(mapped_conditions)} conditions from LLM mapping")
            steps.append(f"   → {len(mapped_conditions)} conditions extraites via LLM")
        else:
            mapped_conditions = []
        
        # Step 2: Identify Candidate Diseases via Vector Search
        explicit_candidates = list(set((candidate_diseases or []) + patient.pathologies + mapped_conditions))
        steps.append(f"2. Candidate diseases prepared: {len(explicit_candidates)}")

        logger.info("Step 3: Running hybrid retrieval (vector + graph)")
        retrieval_result = self.hybrid_retriever.retrieve(patient, explicit_candidates)
        graph_results = retrieval_result.graph_results

        validated = list({item.get("disease") for item in graph_results if item.get("disease")})
        unvalidated = [d for d in explicit_candidates if d not in validated]
        logger.info(
            "Hybrid retrieval results: %s vector matches, %s graph records, %s validated diseases",
            len(retrieval_result.vector_results),
            len(graph_results),
            len(validated),
        )
        steps.append(
            f"3. Hybrid retrieval complete: {len(retrieval_result.vector_results)} vector matches, "
            f"{len(graph_results)} graph records"
        )
        steps.append(f"   → Validées: {len(validated)}, Non trouvées: {len(unvalidated)}")
        
        # Step 4: Generate recommendations
        logger.info(f"Step 4: Generating recommendations for {len(validated)} diseases")
        # Step 4.1: get the elements from the Graph rag ( all relationships )
        # Step 4.2: get RCP  
        recommendations = self.medication_recommender.recommend(
            patient, 
            validated
        )
        logger.info(f"Generated {len(recommendations)} medication recommendations")
        steps.append(f"   → {len(recommendations)} médicaments proposés")
        
        # Step 5: Generate global warnings
        steps.append("5. Génération des alertes contextuelles")
        global_warnings = self.medication_recommender.get_global_warnings(patient)
        steps.append(f"   → {len(global_warnings)} alertes globales")
        
        # Step 6: Generate LLM Report
        logger.info("Step 6: Generating LLM medical report")
        report = self._generate_report(
            patient,
            validated,
            recommendations,
            global_warnings,
            retrieval_result.combined_context,
        )
        steps.append("6. Rédaction du rapport médical (LLM)")
        
        # Step 7: Final Re-validation (Reachability Check)
        logger.info("Step 7: Final re-validation of proposed medicines")
        valid_recs = []
        for rec in recommendations:
            if self._revalidate_medicine_access(rec.medicine_name):
                valid_recs.append(rec)
            else:
                logger.warning(f"Optimization check failed for {rec.medicine_name}, removing.")
                
        steps.append(f"7. Validation finale: {len(valid_recs)}/{len(recommendations)} médicaments confirmés")

        return PrescriptionResult(
            patient=patient,
            validated_diseases=validated,
            unvalidated_diseases=unvalidated,
            recommendations=valid_recs,
            global_warnings=global_warnings,
            processing_steps=steps,
            llm_report=report
        )

    def _revalidate_medicine_access(self, medicine_name: str) -> bool:
        """
        Final sanity check: ensure medicine node exists and is reachable.
        """
        try:
            # Simple existence check
            return self.neo4j_client.get_medicine_details(medicine_name) is not None
        except Exception as e:
            logger.error(f"Revalidation failed for {medicine_name}: {e}")
            return False

    def _generate_report(
        self, 
        patient: PatientContext, 
        diseases: list[str], 
        recommendations: list,
        warnings: list[str],
        combined_context: str,
    ) -> str:
        """
        Generate a professional medical report using LLM.
        """
        try:
            # Check for API key presence                
            client = EdenAIClient(self.config)
            
            # Prepare context for LLM
            meds_list_str = "\\n".join([
                f"- {r.medicine_name} ({r.dosage or 'Dosage standard'}): {r.justification}" 
                for r in recommendations
            ])
            
            warnings_str = "\\n".join(warnings)
            
            prompt = f"""
            Act as a senior Medical Doctor. Write a structured consultation report based on the following context.
            
            PATIENT CONTEXT:
            {patient.to_prompt_text()}
            
            DIAGNOSIS (Validated):
            {', '.join(diseases)}

            GRAPHRAG RETRIEVAL CONTEXT:
            {combined_context}
            
            PROPOSED TREATMENT PLAN:
            {meds_list_str}
            
            WARNINGS & ALERTS:
            {warnings_str}
            
            REPORT FORMAT:
            1. Clinical Summary (Brief recap of patient state)
            2. Diagnosis
            3. Treatment Recommendations (with dosages and justifications)
            4. Safety Alerts & Monitoring (Crucial warnings)
            5. Conclusion
            
            Tone: Professional, clinical, direct. French language.
            """
            
            return client.call_llm(prompt, temperature=0.2)
            
        except Exception as e:
            logger.error(f"Report generation failed: {e}")
            return f"Error generating report: {str(e)}"
