"""Imports precomputed disease embeddings into a Qdrant collection."""

import json
import time
import os
from qdrant_client import QdrantClient
from qdrant_client.http import models

QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "vidal_maladies"
VECTOR_SIZE = 384

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_FILE = os.path.join(BASE_DIR, "data", "disease_embeddings.json")

def import_to_qdrant():
    """Load embedding points from JSON and upsert them into Qdrant."""
    print(f"Connecting to Qdrant at {QDRANT_URL}...")
    client = QdrantClient(url=QDRANT_URL)
    
    # 1. Load data
    print(f"Loading {JSON_FILE}...")
    try:
        with open(JSON_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"❌ File {JSON_FILE} not found!")
        return
        
    points = data.get('points', [])
    print(f"Found {len(points)} points to import.")
    
    # Recreate to keep vector settings aligned with the source embeddings.
    print(f"Recreating collection '{COLLECTION_NAME}'...")
    client.recreate_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=models.VectorParams(
            size=VECTOR_SIZE,
            distance=models.Distance.COSINE
        )
    )
    
    # 3. Upload points
    print("Uploading points...")
    
    # Batch upload for efficiency
    batch_size = 100
    total = len(points)
    
    for i in range(0, total, batch_size):
        batch = points[i:i + batch_size]
        
        qdrant_points = [
            models.PointStruct(
                id=item['id'],
                vector=item['vector'],
                payload=item['payload']
            )
            for item in batch
        ]
        
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=qdrant_points
        )
        print(f"  Processed {min(i + batch_size, total)}/{total}")
        
    print("\n✅ Import completed successfully!")
    
    # 4. Quick verification
    count = client.count(collection_name=COLLECTION_NAME).count
    print(f"Total points in Qdrant: {count}")

if __name__ == "__main__":
    import_to_qdrant()
