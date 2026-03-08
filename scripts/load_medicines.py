"""
Neo4j Medicine Database Importer
Imports the unified medicine JSON directly into Neo4j
"""

import json
from neo4j import GraphDatabase
import time
from collections import defaultdict
import os

class MedicineNeo4jImporter:
    def __init__(self, uri, user, password):
        """Initialize connection to Neo4j"""
        print(f"Connecting to Neo4j at {uri}...")
        try:
            self.driver = GraphDatabase.driver(uri, auth=(user, password))
            # Test connection
            with self.driver.session() as session:
                session.run("RETURN 1")
            print("✓ Connected successfully!")
        except Exception as e:
            print(f"✗ Connection failed: {e}")
            raise
    
    def close(self):
        """Close Neo4j connection"""
        self.driver.close()
    
    def clear_database(self):
        """Clear all nodes and relationships"""
        print("\n⚠️  Clearing database...")
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        print("✓ Database cleared")
    
    def create_constraints(self):
        """Create constraints and indexes for performance"""
        print("\nCreating constraints and indexes...")
        
        constraints = [
            "CREATE CONSTRAINT medicine_name IF NOT EXISTS FOR (m:Medicine) REQUIRE m.name IS UNIQUE",
            "CREATE CONSTRAINT condition_name IF NOT EXISTS FOR (c:Condition) REQUIRE c.name IS UNIQUE",
            "CREATE CONSTRAINT substance_name IF NOT EXISTS FOR (s:ActiveSubstance) REQUIRE s.name IS UNIQUE",
            "CREATE CONSTRAINT class_name IF NOT EXISTS FOR (dc:DrugClass) REQUIRE dc.name IS UNIQUE",
            "CREATE INDEX medicine_name_idx IF NOT EXISTS FOR (m:Medicine) ON (m.name)",
        ]
        
        with self.driver.session() as session:
            for constraint in constraints:
                try:
                    session.run(constraint)
                except Exception as e:
                    # Constraint might already exist
                    pass
        
        print("✓ Constraints created")
    
    def import_medicines(self, json_file, batch_size=100):
        """Import all medicines and create the graph"""
        print(f"\nLoading data from {json_file}...")
        
        with open(json_file, 'r', encoding='utf-8') as f:
            medicines = json.load(f)
        
        total = len(medicines)
        print(f"Found {total} medicines to import")
        
        # Track statistics
        stats = {
            'medicines': 0,
            'conditions': 0,
            'substances': 0,
            'classes': 0,
            'side_effects': 0,
            'interactions': 0,
            'contraindications': 0,
            'warnings': 0,
            'relationships': 0
        }
        
        start_time = time.time()
        
        # Process in batches
        for i in range(0, total, batch_size):
            batch = medicines[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (total + batch_size - 1) // batch_size
            
            print(f"\nProcessing batch {batch_num}/{total_batches} ({len(batch)} medicines)...")
            
            with self.driver.session() as session:
                for med in batch:
                    try:
                        self._import_single_medicine(session, med, stats)
                        stats['medicines'] += 1
                    except Exception as e:
                        print(f"  ⚠️  Error importing {med['name']}: {e}")
            
            # Progress update
            elapsed = time.time() - start_time
            processed = min(i + batch_size, total)
            rate = processed / elapsed if elapsed > 0 else 0
            eta = (total - processed) / rate if rate > 0 else 0
            
            print(f"  Progress: {processed}/{total} ({processed/total*100:.1f}%)")
            print(f"  Rate: {rate:.1f} medicines/sec, ETA: {eta/60:.1f} min")
        
        elapsed = time.time() - start_time
        print(f"\n✓ Import completed in {elapsed/60:.1f} minutes")
        
        return stats
    
    def _import_single_medicine(self, session, med, stats):
        """Import a single medicine with all its relationships"""
        name = med['name']
        
        # 1. Create Medicine node
        session.run("""
            MERGE (m:Medicine {name: $name})
            SET m.url = $url,
                m.pregnancy_info = $pregnancy_info,
                m.breastfeeding_info = $breastfeeding_info,
                m.dosage_general = $dosage_general,
                m.dosage_adult = $dosage_adult,
                m.dosage_child = $dosage_child,
                m.dosage_elderly = $dosage_elderly
        """, 
            name=name,
            url=med['url'],
            pregnancy_info=med['relationships']['pregnancy_info'] or '',
            breastfeeding_info=med['relationships']['breastfeeding_info'] or '',
            dosage_general='; '.join(med['relationships']['dosage'].get('general', [])[:3]),
            dosage_adult='; '.join(med['relationships']['dosage'].get('adult', [])[:3]),
            dosage_child='; '.join(med['relationships']['dosage'].get('child', [])[:3]),
            dosage_elderly='; '.join(med['relationships']['dosage'].get('elderly', [])[:3])
        )
        
        # 2. Create TREATS relationships
        for condition in med['relationships']['treats']:
            if condition and len(condition) > 3:
                session.run("""
                    MATCH (m:Medicine {name: $med_name})
                    MERGE (c:Condition {name: $condition})
                    MERGE (m)-[:TREATS]->(c)
                """, med_name=name, condition=condition)
                stats['conditions'] += 1
                stats['relationships'] += 1
        
        # 3. Create CONTAINS_SUBSTANCE relationships
        for substance in med['substances']['active_substances']:
            if substance and len(substance) > 2:
                # Filter out generic phrases
                if not any(word in substance.lower() for word in 
                          ['comprimé', 'gélule', 'dosage', 'posologie', 'plus de', 'moins de']):
                    session.run("""
                        MATCH (m:Medicine {name: $med_name})
                        MERGE (s:ActiveSubstance {name: $substance})
                        MERGE (m)-[:CONTAINS_SUBSTANCE]->(s)
                    """, med_name=name, substance=substance)
                    stats['substances'] += 1
                    stats['relationships'] += 1
        
        # 4. Create BELONGS_TO_CLASS relationships
        for drug_class in med['substances']['substance_classes']:
            if drug_class and len(drug_class) > 3:
                session.run("""
                    MATCH (m:Medicine {name: $med_name})
                    MERGE (dc:DrugClass {name: $drug_class})
                    MERGE (m)-[:BELONGS_TO_CLASS]->(dc)
                """, med_name=name, drug_class=drug_class)
                stats['classes'] += 1
                stats['relationships'] += 1
        
        # 5. Create HAS_SIDE_EFFECT relationships
        for effect in med['relationships']['side_effects']:
            if effect['effect'] and len(effect['effect']) > 5:
                session.run("""
                    MATCH (m:Medicine {name: $med_name})
                    MERGE (se:SideEffect {name: $effect})
                    MERGE (m)-[r:HAS_SIDE_EFFECT]->(se)
                    SET r.frequency = $frequency
                """, 
                    med_name=name, 
                    effect=effect['effect'][:200], 
                    frequency=effect['frequency']
                )
                stats['side_effects'] += 1
                stats['relationships'] += 1
        
        # 6. Create INTERACTS_WITH relationships
        for interaction in med['relationships']['interacts_with']:
            if interaction and len(interaction) > 10:
                session.run("""
                    MATCH (m:Medicine {name: $med_name})
                    MERGE (i:Interaction {description: $interaction})
                    MERGE (m)-[:INTERACTS_WITH]->(i)
                """, med_name=name, interaction=interaction[:500])
                stats['interactions'] += 1
                stats['relationships'] += 1
        
        # 7. Create CONTRAINDICATED_FOR relationships
        for contra in med['relationships']['contraindications']:
            if contra and len(contra) > 10:
                session.run("""
                    MATCH (m:Medicine {name: $med_name})
                    MERGE (ci:Contraindication {description: $contra})
                    MERGE (m)-[:CONTRAINDICATED_FOR]->(ci)
                """, med_name=name, contra=contra[:500])
                stats['contraindications'] += 1
                stats['relationships'] += 1
        
        # 8. Create HAS_WARNING relationships
        for warning in med['relationships']['warnings']:
            if warning and len(warning) > 10:
                session.run("""
                    MATCH (m:Medicine {name: $med_name})
                    MERGE (w:Warning {text: $warning})
                    MERGE (m)-[:HAS_WARNING]->(w)
                """, med_name=name, warning=warning[:500])
                stats['warnings'] += 1
                stats['relationships'] += 1
    
    def get_statistics(self):
        """Get database statistics"""
        print("\nGathering database statistics...")
        
        with self.driver.session() as session:
            stats = {}
            
            # Count nodes by label
            result = session.run("""
                MATCH (n)
                RETURN labels(n)[0] as Label, count(n) as Count
                ORDER BY Count DESC
            """)
            
            for record in result:
                stats[record['Label']] = record['Count']
            
            # Count relationships by type
            result = session.run("""
                MATCH ()-[r]->()
                RETURN type(r) as Type, count(r) as Count
                ORDER BY Count DESC
            """)
            
            rel_stats = {}
            for record in result:
                rel_stats[record['Type']] = record['Count']
            
            stats['_relationships'] = rel_stats
            
            # Total counts
            result = session.run("MATCH (n) RETURN count(n) as total")
            stats['_total_nodes'] = result.single()['total']
            
            result = session.run("MATCH ()-[r]->() RETURN count(r) as total")
            stats['_total_relationships'] = result.single()['total']
            
            return stats
    
    def verify_import(self):
        """Run verification queries"""
        print("\nRunning verification queries...")
        
        with self.driver.session() as session:
            # Check if we can find medicines
            result = session.run("MATCH (m:Medicine) RETURN count(m) as count")
            medicine_count = result.single()['count']
            
            if medicine_count == 0:
                print("  ✗ No medicines found!")
                return False
            
            print(f"  ✓ Found {medicine_count} medicines")
            
            # Check relationships exist
            result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
            rel_count = result.single()['count']
            
            if rel_count == 0:
                print("  ✗ No relationships found!")
                return False
            
            print(f"  ✓ Found {rel_count} relationships")
            
            # Test a sample query
            result = session.run("""
                MATCH (m:Medicine)-[r]->(n)
                RETURN m.name as medicine, type(r) as relationship, 
                       labels(n)[0] as target
                LIMIT 5
            """)
            
            print("\n  Sample relationships:")
            for record in result:
                print(f"    {record['medicine']} -{record['relationship']}-> {record['target']}")
            
            return True
    
    def print_statistics(self, stats):
        """Print formatted statistics"""
        print("\n" + "=" * 70)
        print("IMPORT STATISTICS")
        print("=" * 70)
        
        print(f"\nTotal Nodes: {stats['_total_nodes']:,}")
        print("-" * 40)
        
        # Sort by count
        node_labels = [(k, v) for k, v in stats.items() 
                      if not k.startswith('_')]
        node_labels.sort(key=lambda x: x[1], reverse=True)
        
        for label, count in node_labels:
            print(f"  {label:25} {count:>10,}")
        
        print(f"\nTotal Relationships: {stats['_total_relationships']:,}")
        print("-" * 40)
        
        if '_relationships' in stats:
            for rel_type, count in stats['_relationships'].items():
                print(f"  {rel_type:25} {count:>10,}")


def main():
    """Main execution function"""
    
    print("=" * 70)
    print("Neo4j Medicine Database Importer")
    print("=" * 70)
    
    # ============================================
    # CONFIGURATION - UPDATE THESE VALUES
    # ============================================
    
    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
    
    if not NEO4J_PASSWORD:
        raise ValueError("NEO4J_PASSWORD environment variable must be set")
    
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    JSON_FILE = os.path.join(BASE_DIR, "data", "medicines_unified.json")
    BATCH_SIZE = 100  # Medicines per batch
    
    # ============================================
    
    print(f"\nConfiguration:")
    print(f"  Neo4j URI: {NEO4J_URI}")
    print(f"  Neo4j User: {NEO4J_USER}")
    print(f"  JSON File: {JSON_FILE}")
    print(f"  Batch Size: {BATCH_SIZE}")
    
    # Confirm before proceeding
    print("\n" + "⚠️ " * 20)
    print("WARNING: This will import data into Neo4j.")
    response = input("\nDo you want to clear the existing database first? (yes/no): ")
    clear_db = response.lower() == 'yes'
    
    try:
        # Initialize importer
        importer = MedicineNeo4jImporter(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
        
        # Clear database if requested
        if clear_db:
            importer.clear_database()
        
        # Create constraints
        importer.create_constraints()
        
        # Import data
        import_stats = importer.import_medicines(JSON_FILE, batch_size=BATCH_SIZE)
        
        # Verify import
        if importer.verify_import():
            print("\n✓ Verification successful!")
        else:
            print("\n✗ Verification failed!")
        
        # Get and display statistics
        db_stats = importer.get_statistics()
        importer.print_statistics(db_stats)
        
        # Close connection
        importer.close()
        
        print("\n" + "=" * 70)
        print("IMPORT COMPLETED SUCCESSFULLY!")
        print("=" * 70)
        print("\nNext steps:")
        print("  1. Open Neo4j Browser: http://localhost:7474")
        print("  2. Try some queries (see NEO4J_GUIDE.md)")
        print("  3. Explore your medicine knowledge graph!")
        
    except Exception as e:
        print(f"\n✗ Error during import: {e}")
        print("\nTroubleshooting:")
        print("  1. Make sure Neo4j is running")
        print("  2. Check your connection URI (bolt:// or neo4j://)")
        print("  3. Verify your username and password")
        print("  4. Ensure the JSON file exists")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
