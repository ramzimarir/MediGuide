"""Text correction utilities for medical transcriptions using Groq LLM."""
from typing import Optional
import logging
import os

from groq import Groq


logger = logging.getLogger("mediguide_server")

_groq_client: Optional[Groq] = None


def _get_groq_client() -> Groq:
    """Initialize or retrieve cached Groq client."""
    global _groq_client
    if _groq_client is None:
        groq_api_key = os.getenv('GROQ_API_KEY')
        if not groq_api_key:
            raise ValueError("GROQ_API_KEY environment variable is required")
        _groq_client = Groq(api_key=groq_api_key)
    return _groq_client


def correct_text_with_groq(raw_text: str) -> str:
    """Correct spelling, grammar, and punctuation in medical text using Groq."""
    if not raw_text or not raw_text.strip():
        return raw_text

    system_prompt = (
        "Tu es un correcteur médical en français. "
        "Corrige l’orthographe, la ponctuation et la grammaire sans changer le sens. "
        "N’ajoute aucune information. Réponds uniquement avec le texte corrigé."
    )

    try:
        groq_client = _get_groq_client()
        completion = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": raw_text}
            ],
            temperature=0.1,
            max_tokens=1200
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Groq text correction error: {e}")
        return raw_text