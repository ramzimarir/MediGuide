"""Audio transcription using Groq Whisper API. Lazy-initialized to avoid blocking startup on missing API keys."""
import os
import logging
from typing import Optional
from groq import Groq

# Configuration Logger
logger = logging.getLogger(__name__)

_client: Optional[Groq] = None

def _get_client() -> Groq:
    """Lazy initialization of Groq client."""
    global _client
    if _client is None:
        api_key = os.getenv('GROQ_API_KEY')
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable is required")
        _client = Groq(api_key=api_key)
    return _client

def transcribe(audio_path: str, language: str = "fr") -> str:
    """Transcribe audio file to text using Groq Whisper. Returns empty string on error."""
    if not os.path.exists(audio_path):
        logger.error(f"Audio file not found: {audio_path}")
        return ""

    try:
        client = _get_client()
        logger.info(f"🚀 Sending to Groq Whisper: {audio_path}")
        
        with open(audio_path, "rb") as file:
            transcription = client.audio.transcriptions.create(
                file=(os.path.basename(audio_path), file.read()),
                model="whisper-large-v3",
                language=language,
                temperature=0.0,
                response_format="json"
            )
        
        text = transcription.text.strip()
        logger.info(f"✅ Transcription received ({len(text)} chars)")
        return text

    except Exception as e:
        logger.error(f"❌ Groq Whisper error: {e}")
        return "[Transcription error]"
