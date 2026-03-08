"""Local embedding generation utilities with lazy model initialization."""
from typing import Optional
import logging
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

MODEL_NAME = 'all-MiniLM-L6-v2'
_EMBEDDER: Optional[SentenceTransformer] = None

def _get_embedder() -> SentenceTransformer:
    """Lazy initialization of embedding model."""
    global _EMBEDDER
    if _EMBEDDER is None:
        try:
            logger.info(f"Loading embedding model: {MODEL_NAME}")
            _EMBEDDER = SentenceTransformer(MODEL_NAME)
            logger.info("Embedding model loaded.")
        except Exception as e:
            logger.error(f"Embedding model load error: {e}")
            raise RuntimeError(f"Embedding model could not be loaded: {e}")
    return _EMBEDDER

def get_embedding(text: str):
    """Generate embedding vector for input text. Returns a list of floats."""
    embedder = _get_embedder()
    vector = embedder.encode(text)
    return vector.tolist()
