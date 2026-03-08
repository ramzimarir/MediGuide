"""Note summarization utilities for medical text extraction."""
import re
from datetime import datetime
from typing import Dict, List, Optional

KEYWORDS = [
    "motif", "plainte", "symptômes", "symptome", "antécédents", "traitement",
    "médicament", "medicament", "diagnostic", "examen", "imagerie", "conclusion",
    "allergie", "atcd", "tension", "ta", "poids", "taille"
]


def _format_date(ts: Optional[str]) -> str:
    """Format ISO timestamp to readable DD/MM/YYYY HH:MM format."""
    if not ts:
        return "Unknown date"
    try:
        dt = datetime.fromisoformat(ts)
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return ts


def _strip_html(text: str) -> str:
    """Remove HTML tags from text."""
    return re.sub(r"<[^>]+>", " ", text or "")


def summarize_note(text: str, timestamp: Optional[str] = None, client=None) -> Dict[str, object]:
    """Summarize medical note using LLM or fallback to keyword extraction."""
    clean = _strip_html(text)
    clean = re.sub(r"\s+", " ", clean).strip()

    if client and clean:
        system_prompt = (
            "Tu es un assistant médical. Donne uniquement 3 à 5 puces courtes, "
            "sans titre ni phrase d'introduction. N'ajoute AUCUNE information qui "
            "n'existe pas dans le texte. Ne déduis rien."
        )

        try:
            completion = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": clean}
                ],
                temperature=0.0,
                max_tokens=220
            )

            result = completion.choices[0].message.content.strip()
            lines = []
            for ln in result.split("\n"):
                cleaned = ln.strip().lstrip("-• ").strip()
                if not cleaned:
                    continue
                lower = cleaned.lower()
                if lower.startswith("voici") or "résumé" in lower or "resume" in lower:
                    continue
                lines.append(cleaned)
            return {"date": _format_date(timestamp), "summary": lines[:5]}
        except Exception:
            pass

    lines: List[str] = []
    if clean:
        sentences = re.split(r"(?<=[\.\!\?])\s+", clean)
        for sentence in sentences:
            if any(k.lower() in sentence.lower() for k in KEYWORDS):
                lines.append(sentence.strip())
            if len(lines) >= 4:
                break

        if not lines:
            lines = [s.strip() for s in sentences[:3] if s.strip()]

    if not lines and clean:
        lines = [clean[:300] + ("..." if len(clean) > 300 else "")]

    return {
        "date": _format_date(timestamp),
        "summary": lines
    }
