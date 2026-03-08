"""Builds and uploads Neo4j condition embeddings into Qdrant."""

import os
import sys
from typing import List, Dict
from qdrant_client import QdrantClient, models
from qdrant_client.http.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer
from fastembed import TextEmbedding
from tqdm import tqdm

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

from storage.neo4j_client import Neo4jClient
from shared.config import Config
from shared.logger import logger, setup_logger

# Configuration
COLLECTION_NAME = "neo4j_conditions"
VECTOR_SIZE = 384  # Matching the model size
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# Setup logger for this script
script_logger = setup_logger("condition_indexer")

def fetch_conditions_from_neo4j() -> List[str]:
    """Fetch all unique condition names from Neo4j."""
    script_logger.info("Fetching conditions from Neo4j...")
    with Neo4jClient() as client:
        with client.driver.session() as session:
            # Fetch all conditions
            query = "MATCH (c:Condition) RETURN c.name as name"
            result = session.run(query)
            conditions = [record["name"] for record in result if record["name"]]
            
    script_logger.info(f"Found {len(conditions)} conditions in Neo4j.")
    return list(set(conditions))  # Ensure uniqueness

def index_conditions(conditions: List[str]):
    """Generate embeddings and index condition names into Qdrant."""
    
    # Initialize Qdrant client
    config = Config.get_instance()
    qdrant_url = getattr(config, "QDRANT_URL", "http://localhost:6333")
    client = QdrantClient(url=qdrant_url)
    
    # Initialize embedding model
    script_logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
    model = TextEmbedding(model_name=EMBEDDING_MODEL)

    # Check and Recreate Collection
    if client.collection_exists(COLLECTION_NAME):
        script_logger.info(f"Collection '{COLLECTION_NAME}' exists. Recreating...")
        client.delete_collection(COLLECTION_NAME)
    
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE)
    )
    script_logger.info(f"Created collection '{COLLECTION_NAME}'.")

    # Generate Embeddings and Index
    points = []
    script_logger.info("Generating embeddings and preparing points...")
    
    # Encode all texts at once (or in batches if too large, but conditions list should be manageable)
    # FastEmbed generator
    embeddings = list(model.embed(conditions))
    
    for i, (condition, vector) in enumerate(zip(conditions, embeddings)):
        points.append(PointStruct(
            id=i,
            vector=vector.tolist(),
            payload={"name": condition}
        ))
    
    # Upload in batches
    batch_size = 100
    script_logger.info(f"Uploading {len(points)} points to Qdrant...")
    
    for i in tqdm(range(0, len(points), batch_size)):
        batch = points[i:i + batch_size]
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=batch
        )
        
    script_logger.info("Indexing complete!")

def main():
    """Run condition extraction from Neo4j and indexing to Qdrant."""
    try:
        conditions = fetch_conditions_from_neo4j()
        if not conditions:
            script_logger.warning("No conditions found in Neo4j. Aborting.")
            return
            
        index_conditions(conditions)
        
    except Exception as e:
        script_logger.error(f"Failed to index conditions: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
