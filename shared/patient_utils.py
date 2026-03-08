"""Utility helpers for patient normalization and note section parsing."""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import os
import json
import logging

from shared.paths import DB_ROOT


logger = logging.getLogger("mediguide_server")


def _is_valid_iso(ts: str) -> bool:
    """Return True when timestamp is a valid ISO-8601 string."""
    try:
        datetime.fromisoformat(ts)
        return True
    except Exception:
        return False


def backfill_note_timestamps() -> None:
    """Fill missing or invalid note timestamps for existing local records."""
    try:
        if not os.path.exists(DB_ROOT):
            return

        for patient_dir in os.scandir(DB_ROOT):
            if not patient_dir.is_dir():
                continue

            note_files = [
                f for f in os.scandir(patient_dir.path)
                if f.is_file() and f.name.endswith(".json") and f.name != "patient_info.json"
            ]

            # Sort newest first to keep deterministic fallback chronology.
            note_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

            for idx, note_file in enumerate(note_files):
                try:
                    with open(note_file.path, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    ts = data.get("timestamp")
                    if not ts or not isinstance(ts, str) or not _is_valid_iso(ts):
                        base = datetime.utcnow() - timedelta(days=idx % 60, hours=idx % 24)
                        data["timestamp"] = base.isoformat()

                        with open(note_file.path, 'w', encoding='utf-8') as f:
                            json.dump(data, f, ensure_ascii=False, indent=2)
                except Exception:
                    continue
    except Exception as e:
        logger.warning(f"Backfill timestamps error: {e}")


def _calc_age(date_str: Optional[str]) -> Optional[int]:
    """Compute age from date string when parsing succeeds."""
    if not date_str:
        return None
    try:
        dt = datetime.fromisoformat(date_str)
    except Exception:
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        except Exception:
            return None
    today = datetime.utcnow().date()
    return today.year - dt.year - ((today.month, today.day) < (dt.month, dt.day))


def _map_sex(gender: Optional[str]) -> Optional[str]:
    """Map gender text variants to canonical M/F values."""
    if not gender:
        return None
    g = gender.strip().lower()
    if g in ("male", "mâle", "m"): return "M"
    if g in ("female", "femelle", "f"): return "F"
    return None


def _extract_sections(filtered_text: str) -> Dict[str, List[str]]:
    """Parse sectioned markdown note text into structured buckets."""
    sections = {
        "symptoms": [],
        "motifs": [],
        "clinical": [],
        "pathologies": [],
        "treatments": [],
        "exams": [],
        "antecedents": []
    }

    if not filtered_text:
        return sections

    current = None
    for line in filtered_text.split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("###"):
            title = line.replace("###", "").strip().upper()
            if "SYMPTÔMES" in title or "SYMPTOMES" in title or "MOTIFS" in title:
                current = "symptoms"
            elif "DONNÉES" in title or "DONNEES" in title or "MESURES" in title:
                current = "clinical"
            elif "PATHOLOGIES" in title:
                current = "pathologies"
            elif "TRAITEMENTS" in title or "MÉDICAMENTS" in title or "MEDICAMENTS" in title:
                current = "treatments"
            elif "EXAMENS" in title or "ACTES" in title:
                current = "exams"
            elif "CONTEXTE" in title:
                current = "antecedents"
            else:
                current = None
            continue

        if line.startswith("•"):
            item = line.lstrip("•").strip()
            if current and item:
                sections[current].append(item)

    return sections


def _extract_clinical_data(items: List[str]) -> Dict[str, Any]:
    """Extract key-value clinical measurements from list items."""
    data: Dict[str, Any] = {}
    for item in items:
        if ":" in item:
            k, v = item.split(":", 1)
            data[k.strip()] = v.strip()
    return data