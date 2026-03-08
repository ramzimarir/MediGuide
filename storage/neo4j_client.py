"""
Neo4j client for the Medical Prescription System.
Provides query methods for medicine recommendations and validations.
"""

from typing import Optional
from neo4j import GraphDatabase

from shared.config import Config
from shared.logger import logger


class Neo4jClient:
    """
    Client for interacting with the Neo4j medicine knowledge graph.
    """
    
    def __init__(self, config: Optional[Config] = None):
        """
        Initialize Neo4j connection.
        
        Args:
            config: Configuration object. If None, uses singleton instance.
        """
        self.config = config or Config.get_instance()
        self.driver = GraphDatabase.driver(
            self.config.neo4j.uri,
            auth=(self.config.neo4j.user, self.config.neo4j.password)
        )
        logger.info(f"Neo4j client initialized, connected to {self.config.neo4j.uri}")
        # Test connection
        with self.driver.session() as session:
            session.run("RETURN 1")
    
    def close(self):
        """Close the Neo4j connection"""
        self.driver.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    # =========================================================================
    # Condition/Disease Queries
    # =========================================================================
    
    def find_condition(self, condition_name: str, fuzzy: bool = True) -> list[dict]:
        """
        Find conditions in the database matching the given name.
        
        Args:
            condition_name: Name to search for
            fuzzy: If True, uses CONTAINS for partial matching
            
        Returns:
            List of matching conditions with their names
        """
        with self.driver.session() as session:
            if fuzzy:
                query = """
                    MATCH (c:Condition)
                    WHERE toLower(c.name) CONTAINS toLower($name)
                    RETURN c.name as name
                    LIMIT 20
                """
            else:
                query = """
                    MATCH (c:Condition {name: $name})
                    RETURN c.name as name
                """
            result = session.run(query, name=condition_name)
            return [dict(record) for record in result]
    
    def validate_conditions(self, conditions: list[str]) -> dict[str, list[str]]:
        """
        Validate a list of conditions against the database.
        
        Args:
            conditions: List of condition names to validate
            
        Returns:
            Dict with 'validated' and 'unvalidated' lists
        """
        validated = []
        unvalidated = []
        
        for condition in conditions:
            matches = self.find_condition(condition)
            if matches:
                validated.append(condition)
            else:
                unvalidated.append(condition)
        
        return {"validated": validated, "unvalidated": unvalidated}
    
    # =========================================================================
    # Medicine Queries
    # =========================================================================
    
    def find_medicines_for_condition(self, condition: str, limit: int = 20) -> list[dict]:
        """
        Find medicines that treat a given condition.
        
        Args:
            condition: Condition name (uses fuzzy matching)
            limit: Maximum number of results
            
        Returns:
            List of medicines with their details
        """
        with self.driver.session() as session:
            query = """
                MATCH (m:Medicine)-[:TREATS]->(c:Condition)
                WHERE toLower(c.name) CONTAINS toLower($condition)
                RETURN DISTINCT 
                    m.name as name,
                    m.url as url,
                    m.dosage_general as dosage_general,
                    m.dosage_adult as dosage_adult,
                    m.dosage_child as dosage_child,
                    m.dosage_elderly as dosage_elderly,
                    m.frequency as frequency,
                    m.pregnancy_info as pregnancy_info,
                    m.breastfeeding_info as breastfeeding_info,
                    collect(DISTINCT c.name) as treats
                LIMIT $limit
            """
            result = session.run(query, condition=condition, limit=limit)
            return [dict(record) for record in result]
    
    def get_medicine_details(self, medicine_name: str) -> Optional[dict]:
        """
        Get full details of a medicine.
        
        Args:
            medicine_name: Exact medicine name
            
        Returns:
            Medicine details or None if not found
        """
        with self.driver.session() as session:
            query = """
                MATCH (m:Medicine {name: $name})
                OPTIONAL MATCH (m)-[:TREATS]->(c:Condition)
                OPTIONAL MATCH (m)-[:CONTAINS_SUBSTANCE]->(s:ActiveSubstance)
                OPTIONAL MATCH (m)-[:BELONGS_TO_CLASS]->(dc:DrugClass)
                OPTIONAL MATCH (m)-[:HAS_SIDE_EFFECT]->(se:SideEffect)
                OPTIONAL MATCH (m)-[:INTERACTS_WITH]->(i:Interaction)
                OPTIONAL MATCH (m)-[:CONTRAINDICATED_FOR]->(ci:Contraindication)
                OPTIONAL MATCH (m)-[:HAS_WARNING]->(w:Warning)
                RETURN 
                    m.name as name,
                    m.url as url,
                    m.dosage_general as dosage_general,
                    m.dosage_adult as dosage_adult,
                    m.dosage_child as dosage_child,
                    m.dosage_elderly as dosage_elderly,
                    m.frequency as frequency,
                    m.pregnancy_info as pregnancy_info,
                    m.breastfeeding_info as breastfeeding_info,
                    collect(DISTINCT c.name) as treats,
                    collect(DISTINCT s.name) as substances,
                    collect(DISTINCT dc.name) as drug_classes,
                    collect(DISTINCT se.name) as side_effects,
                    collect(DISTINCT i.description) as interactions,
                    collect(DISTINCT ci.description) as contraindications,
                    collect(DISTINCT w.text) as warnings
            """
            result = session.run(query, name=medicine_name)
            record = result.single()
            return dict(record) if record else None
    
    # =========================================================================
    # Warning & Safety Queries
    # =========================================================================
    
    def get_warnings_for_medicine(self, medicine_name: str) -> list[str]:
        """Get all warnings for a medicine"""
        with self.driver.session() as session:
            query = """
                MATCH (m:Medicine {name: $name})-[:HAS_WARNING]->(w:Warning)
                RETURN w.text as warning
            """
            result = session.run(query, name=medicine_name)
            return [record["warning"] for record in result]
    
    def get_contraindications_for_medicine(self, medicine_name: str) -> list[str]:
        """Get contraindications for a medicine"""
        with self.driver.session() as session:
            query = """
                MATCH (m:Medicine {name: $name})-[:CONTRAINDICATED_FOR]->(ci:Contraindication)
                RETURN ci.description as contraindication
            """
            result = session.run(query, name=medicine_name)
            return [record["contraindication"] for record in result]
    
    def get_interactions_for_medicine(self, medicine_name: str) -> list[str]:
        """Get drug interactions for a medicine"""
        with self.driver.session() as session:
            query = """
                MATCH (m:Medicine {name: $name})-[:INTERACTS_WITH]->(i:Interaction)
                RETURN i.description as interaction
            """
            result = session.run(query, name=medicine_name)
            return [record["interaction"] for record in result]
    
    def check_patient_contraindications(
        self, 
        medicine_name: str, 
        patient_conditions: list[str]
    ) -> list[str]:
        """
        Check if any patient conditions are contraindicated for a medicine.
        
        Args:
            medicine_name: Medicine to check
            patient_conditions: List of patient's conditions/antecedents
            
        Returns:
            List of relevant warning messages
        """
        warnings = []
        
        # Get all contraindications and warnings for the medicine
        contraindications = self.get_contraindications_for_medicine(medicine_name)
        med_warnings = self.get_warnings_for_medicine(medicine_name)
        
        # Check each contraindication/warning against patient conditions
        for patient_cond in patient_conditions:
            patient_cond_lower = patient_cond.lower()
            
            for contra in contraindications:
                if patient_cond_lower in contra.lower():
                    warnings.append(f"⚠️ CONTRE-INDICATION: {contra} (patient a: {patient_cond})")
            
            for warning in med_warnings:
                if patient_cond_lower in warning.lower():
                    warnings.append(f"⚠️ ATTENTION: {warning} (patient a: {patient_cond})")
        
        return warnings
    
    def get_evidence_subgraph(
        self, 
        medicine_name: str, 
        patient_conditions: list[str],
        targets: list[str]
    ) -> dict:
        """
        Produce a subgraph (nodes and links) and a Cypher query that 
        justifies the relationship between the drug and the patient's state.
        
        Returns:
            Dict containing 'query', 'nodes', and 'edges'
        """
        # 1. Build a Cypher query that highlights:
        # - The Medicine
        # - The Conditions it TREATS that match patient's targets
        # - The Warnings/Contraindications that match patient's antecedents
        
        query = """
        MATCH (m:Medicine {name: $medicine_name})
        OPTIONAL MATCH (m)-[r1:TREATS]->(c:Condition)
        WHERE any(target IN $targets WHERE toLower(c.name) CONTAINS toLower(target))
        OPTIONAL MATCH (m)-[r2:HAS_WARNING|CONTRAINDICATED_FOR]->(w)
        WHERE any(cond IN $patient_conditions WHERE toLower(w.description) CONTAINS toLower(cond) OR toLower(w.text) CONTAINS toLower(cond))
        RETURN m, r1, c, r2, w
        """

        params = {
            "medicine_name": medicine_name,
            "targets": targets,
            "patient_conditions": patient_conditions,
        }
        
        # Simplified data extraction for demonstration
        # In a real app, we would run this and parse nodes/edges
        return {
            "query": query.strip(),
            "params": params,
            "target_med": medicine_name,
            "highlight_conditions": targets,
            "search_warnings": patient_conditions
        }
    
    # =========================================================================
    # Statistics & Utility
    # =========================================================================
    
    def get_statistics(self) -> dict:
        """Get database statistics"""
        with self.driver.session() as session:
            stats = {}
            
            # Count by label
            result = session.run("""
                MATCH (n)
                RETURN labels(n)[0] as label, count(n) as count
                ORDER BY count DESC
            """)
            stats["nodes"] = {r["label"]: r["count"] for r in result}
            
            # Total relationships
            result = session.run("MATCH ()-[r]->() RETURN count(r) as total")
            stats["total_relationships"] = result.single()["total"]
            
            return stats
