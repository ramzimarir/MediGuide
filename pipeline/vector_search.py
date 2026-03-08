
from typing import List, Optional
from qdrant_client import QdrantClient
from fastembed import TextEmbedding

from shared.models import PatientContext
from shared.logger import logger

EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"  # If exact alias shown

class VectorSearchService:
    """
    Service to search for disease candidates using vector similarity.
    Uses Qdrant for storage and SentenceTransformers for local query embedding.
    """
    
    def __init__(self, collection_name: str = "vidal_maladies", url: str = "http://localhost:6333"):
        self.collection_name = collection_name
        self.client = QdrantClient(url=url)
        # Keep embedding model aligned with indexed vectors to preserve similarity quality.

        self.embedding_model = TextEmbedding(model_name=EMBEDDING_MODEL)

    def search_diseases(self, patient: PatientContext, limit: int = 5) -> List[str]:
        """
        Search for diseases matching the patient context.
        """
        # Construct search query from patient data
        query_text = self._build_query_text(patient)
        
        # Generate embedding for the query text
        # fastembed returns a generator of vectors (numpy arrays)
        query_vector = list(self.embedding_model.embed([query_text]))[0].tolist()
        logger.info(f"Generated query vector (size={len(query_vector)}) for text: {query_text[:50]}...")
        
        results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,  # Or QueryPoint(vector=query_vector) for complex queries
            limit=limit
        ).points 
        
        # Extract disease names
        candidates = []
        for hit in results:
            if hit.payload:
                # Prefer title, fallback to page_title
                name = hit.payload.get("title") or hit.payload.get("page_title")
                if name:
                    candidates.append(name)
        
        logger.info(f"Vector search returned {len(candidates)} candidates: {candidates}")
        return candidates

    def _build_query_text(self, patient: PatientContext) -> str:
        """Construct a search query from patient attributes."""
        parts = []
        
        # Prioritize high-signal clinical fields for retrieval relevance.
        if patient.symptoms:
            parts.append(f"Symptômes: {', '.join(patient.symptoms)}")
            
        if patient.pathologies:
            parts.append(f"Pathologies connues: {', '.join(patient.pathologies)}")
            
            
        if patient.antecedents:
            parts.append(f"Antécédents: {', '.join(patient.antecedents)}")
            
        return ". ".join(parts)

    def search_neo4j_conditions(self, query_text: str, limit: int = 3) -> List[dict]:
        """
        Search for the closest Neo4j condition using vector similarity.
        Used to semantically validate a disease candidate against the graph.
        
        Args:
            query_text: The disease name or description to match
            limit: Number of results
            
        Returns:
            List of dicts with 'name', 'score'
        """
        collection = "neo4j_conditions"
        
        try:
            # Generate embedding
            # fastembed returns a generator of vectors (numpy arrays)
            query_vector = list(self.embedding_model.embed([query_text]))[0].tolist()
            
            results = self.client.query_points(
                collection_name=collection,
                query=query_vector,
                limit=limit
            ).points
            
            matches = []
            for hit in results:
                if hit.payload:
                    matches.append({
                        "name": hit.payload.get("name"),
                        "score": hit.score
                    })
            
            return matches
            
        except Exception as e:
            logger.error(f"Semantic search for condition '{query_text}' failed: {e}")
            return []
