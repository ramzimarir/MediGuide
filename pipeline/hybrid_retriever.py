from dataclasses import dataclass

from storage.neo4j_client import Neo4jClient
from pipeline.vector_search import VectorSearchService
from pipeline.disease_validator import DiseaseValidator
from shared.models import PatientContext
from shared.logger import logger


@dataclass
class RetrievalResult:
    query: str
    vector_results: list[dict]
    graph_results: list[dict]
    combined_context: str


class HybridRetriever:
    def __init__(
        self,
        neo4j_client: Neo4jClient,
        vector_search_service: VectorSearchService,
        disease_validator: DiseaseValidator,
    ):
        self.neo4j_client = neo4j_client
        self.vector_search_service = vector_search_service
        self.disease_validator = disease_validator

    def retrieve(
        self,
        patient_context: PatientContext,
        candidate_diseases: list[str] | None,
    ) -> RetrievalResult:
        # Step 1: semantic candidates from Qdrant
        semantic_candidates = self.vector_search_service.search_diseases(patient_context)
        vector_results = [
            {"disease": disease, "score": None}
            for disease in semantic_candidates
            if disease
        ]

        # Step 3: validate and filter diseases using semantic + explicit candidates
        requested_candidates = candidate_diseases or []
        all_candidates = list(dict.fromkeys(requested_candidates + semantic_candidates))
        validation = self.disease_validator.validate_diseases(
            all_candidates,
            vector_search_service=self.vector_search_service,
        )
        validated_diseases = [item["matched"] for item in validation.get("validated", [])]

        # Step 2: graph retrieval for each validated disease
        graph_results = []
        for disease in validated_diseases:
            medicines = self.neo4j_client.find_medicines_for_condition(disease, limit=5)
            for med in medicines:
                details = self.neo4j_client.get_medicine_details(med["name"]) or {}
                graph_results.append(
                    {
                        "disease": disease,
                        "medicine": med.get("name"),
                        "treats": details.get("treats") or med.get("treats") or [],
                        "substances": details.get("substances") or [],
                        "warnings": details.get("warnings") or [],
                        "contraindications": details.get("contraindications") or [],
                    }
                )

        combined_context = self._build_combined_context(vector_results, graph_results)
        logger.info(
            "Hybrid retrieval complete: %s vector matches, %s graph records",
            len(vector_results),
            len(graph_results),
        )

        return RetrievalResult(
            query=patient_context.to_prompt_text(),
            vector_results=vector_results,
            graph_results=graph_results,
            combined_context=combined_context,
        )

    def _build_combined_context(self, vector_results: list[dict], graph_results: list[dict]) -> str:
        lines = ["## Semantic matches (vector search)"]
        if vector_results:
            for item in vector_results:
                disease = item.get("disease", "Unknown")
                score = item.get("score")
                score_text = f"{score:.2f}" if isinstance(score, (int, float)) else "N/A"
                lines.append(f"- {disease} (score: {score_text})")
        else:
            lines.append("- No semantic matches found")

        lines.append("")
        lines.append("## Medical knowledge (graph)")
        if graph_results:
            for item in graph_results:
                lines.append(f"### {item.get('medicine', 'Unknown medicine')}")
                lines.append(f"- Treats: {', '.join(item.get('treats', [])) or 'N/A'}")
                lines.append(f"- Substances: {', '.join(item.get('substances', [])) or 'N/A'}")
                lines.append(f"- Warnings: {', '.join(item.get('warnings', [])) or 'N/A'}")
                lines.append(
                    f"- Contraindications: {', '.join(item.get('contraindications', [])) or 'N/A'}"
                )
        else:
            lines.append("- No graph knowledge found for validated diseases")

        return "\n".join(lines)
