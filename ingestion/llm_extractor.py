"""src.core.llm_extractor
LLM-based structured medical information extractor (Via Groq/Llama 3)
Extracts and structures medical data from clinical text using LLM prompts.

NOTE: Lazy initialization - client created on first use to avoid
blocking startup if GROQ_API_KEY is missing.
"""
import logging
import os
from typing import Optional
from groq import Groq

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
        logger.info("✅ Client Groq (Extraction) initialisé.")
    return _client

def process_text(raw_text: str) -> str:
    """Extract and structure medical data from raw text using Llama 3. Filters empty or unknown fields."""
    try:
        client = _get_client()
    except ValueError:
        # If no API key, return raw text
        return raw_text
    
    system_prompt = """
    Tu es un extracteur de données médicales de précision.
    Ton rôle est de structurer les informations PRÉSENTES dans le texte.

    RÈGLES DE SILENCE (CRITIQUES) :
    1. Si une information n'est pas explicite dans le texte, NE L'ÉCRIS PAS.
    2. INTERDICTION FORMELLE d'écrire les mots : "inconnu", "non précisé", "non mentionné", "N/A", "non renseigné".
    3. Si une section (ex: CONTEXTE PATIENT) est vide après ce filtrage, NE L'AFFICHE PAS du tout.
    4. Évite les répétitions : Si "Syndrome asthmatique" est déjà dans "Pathologies", ne le remets pas dans "Antécédents" sauf si c'est précisé "Antécédent de...".

    FORMAT DE SORTIE ATTENDU :
    Utilise exactement ce format (Markdown). Si une ligne est vide, supprime-la.

    ### CONTEXTE PATIENT
    • [Age, Sexe - UNIQUEMENT SI PRÉSENTS]
    • [Antécédents précis]

    ### SYMPTÔMES & MOTIFS
    • [Liste des plaintes actuelles]

    ### DONNÉES CLINIQUES & MESURES
    • [Constantes chiffrées : TA, Sat, Température...]

    ### PATHOLOGIES IDENTIFIÉES
    • [Diagnostics posés]

    ### TRAITEMENTS & MÉDICAMENTS
    • [Molécules, Dosages, Voies d'administration]

    ### EXAMENS & ACTES
    • [Actes réalisés ou prescrits]
    """

    user_prompt = f"Voici la note brute, extrais SEULEMENT ce qui existe : \n\n{raw_text}"

    try:
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.0,
            max_tokens=1000
        )
        
        # Post-process output to ensure LLM didn't violate silence rules
        result = completion.choices[0].message.content.strip()
        cleaned_lines = []
        
        # On supprime manuellement les lignes qui auraient échappé au filtre
        for line in result.split('\n'):
            line_lower = line.lower()
            if "inconnu" in line_lower or "non précisé" in line_lower or "non mentionné" in line_lower:
                continue
            if line.strip() == "•": 
                continue
            cleaned_lines.append(line)
            
        return "\n".join(cleaned_lines).strip()

    except Exception as e:
        logger.error(f"Groq extraction error: {e}")
        return raw_text
