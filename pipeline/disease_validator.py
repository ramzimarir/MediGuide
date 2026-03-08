"""
Disease Validator for the Medical Prescription System.
Validates diseases against the Neo4j knowledge graph.
"""

from typing import Optional

from shared.config import Config
from storage.neo4j_client import Neo4jClient
from shared.logger import logger


class DiseaseValidator:
    """
    Validates diseases/conditions against the knowledge graph.
    Uses fuzzy matching to find corresponding entries.
    """
    
    def __init__(self, config: Optional[Config] = None, neo4j_client: Optional[Neo4jClient] = None):
        """
        Initialize the disease validator.
        
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
    
    def validate_diseases(self, diseases: list[str], vector_search_service = None) -> dict:
        """
        Validate a list of diseases against the knowledge graph.
        Prioritizes Semantic Search (Qdrant) over Fuzzy Match (Neo4j string).
        
        Args:
            diseases: List of disease/condition names to validate
            vector_search_service: Optional VectorSearchService instance. 
                                      If None, falls back to Neo4j fuzzy match.
        
        Returns:
            Dictionary with:
                - validated: List of (original, matched_in_db, score, method) tuples
                - unvalidated: List of diseases not found
        """
        logger.info(f"Validating {len(diseases)} diseases against graph (Semantic Check)")
        validated = []
        unvalidated = []
        
        for disease in diseases:
            match_found = False
            
            # 1. Try Semantic Search first (if service available)
            if vector_search_service:
                semantic_matches = vector_search_service.search_neo4j_conditions(disease, limit=1)
                
                if semantic_matches and semantic_matches[0]["score"] > 0.9:
                    best_match = semantic_matches[0]
                    matched_name = best_match["name"]
                    score = best_match["score"]
                    
                    logger.info(f"✓ Semantic Match: '{disease}' -> '{matched_name}' (Score: {score:.4f})")
                    
                    validated.append({
                        "original": disease,
                        "matched": matched_name,
                        "method": "semantic",
                        "score": score
                    })
                    match_found = True
            
            # 2. Fallback to Neo4j Fuzzy Search if no semantic match (or service missing)
            if not match_found:
                matches = self.neo4j.find_condition(disease, fuzzy=True)
                if matches:
                    matched_name = matches[0]["name"]
                    logger.info(f"✓ Fuzzy Match: '{disease}' -> '{matched_name}'")
                    validated.append({
                        "original": disease,
                        "matched": matched_name,
                        "method": "fuzzy",
                        "score": 1.0 # Pseudo-score
                    })
                    match_found = True
            
            if not match_found:
                logger.warning(f"✗ No match found for '{disease}'")
                unvalidated.append(disease)
        
        logger.info(f"Disease validation finished: {len(validated)} validated, {len(unvalidated)} failed")
        return {
            "validated": validated,
            "unvalidated": unvalidated
        }

    
    def find_best_match(self, disease: str) -> Optional[str]:
        """
        Find the best matching condition in the database.
        
        Args:
            disease: Disease name to match
            
        Returns:
            Best matching condition name, or None if no match
        """
        matches = self.neo4j.find_condition(disease, fuzzy=True)
        return matches[0]["name"] if matches else None
    
    def get_related_conditions(self, disease: str) -> list[str]:
        """
        Get conditions that might be related to the given disease.
        Useful for suggestions when exact match not found.
        
        Args:
            disease: Disease name
            
        Returns:
            List of potentially related condition names
        """
        # Extract keywords from disease name
        keywords = disease.lower().split()
        
        related = set()
        for keyword in keywords:
            if len(keyword) > 3:  # Skip short words
                matches = self.neo4j.find_condition(keyword, fuzzy=True)
                for match in matches[:5]:
                    related.add(match["name"])
        
        return list(related)[:10]
