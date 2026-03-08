from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
import json
import os

from shared.paths import DB_ROOT


class NoteRepository:
    """Persists notes and draft notes on local JSON storage."""
    def __init__(self, db_root: Path = DB_ROOT) -> None:
        """Initialize repository with storage root path."""
        self.db_root = Path(db_root)

    def save_note(self, patient_id: str, note_data: Dict[str, Any]) -> None:
        """Save a note JSON file under the patient directory."""
        patient_dir = self.db_root / patient_id
        if not patient_dir.exists():
            raise FileNotFoundError("Patient introuvable")
        note_id = str(note_data.get("id", "")).strip()
        if not note_id:
            raise ValueError("id de note manquant")
        with (patient_dir / f"{note_id}.json").open("w", encoding="utf-8") as f:
            json.dump(note_data, f, ensure_ascii=False, indent=2)

    def delete_note(self, patient_id: str, note_id: str) -> None:
        """Delete a note file for a patient by note ID."""
        safe_id = os.path.basename(note_id)
        note_path = self.db_root / patient_id / f"{safe_id}.json"
        if not note_path.exists():
            raise FileNotFoundError("Not found")
        note_path.unlink()

    def delete_note_by_item_id(self, note_id: str) -> str:
        """Delete note by ID across all patients. Returns deleted note ID."""
        safe_id = os.path.basename(note_id)
        for patient_dir in self.db_root.iterdir() if self.db_root.exists() else []:
            if not patient_dir.is_dir():
                continue
            note_path = patient_dir / f"{safe_id}.json"
            if note_path.exists():
                self.delete_note(patient_dir.name, safe_id)
                return safe_id
        raise FileNotFoundError("Not found")

    def get_draft(self, patient_id: str, session_id: str = "default") -> Optional[Dict[str, Any]]:
        """Load draft content for a patient session if it exists."""
        draft_path = self.db_root / patient_id / "_drafts" / f"{session_id}.json"
        if not draft_path.exists():
            return None
        with draft_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def save_draft(self, patient_id: str, text: str, session_id: str = "default") -> None:
        """Persist draft text for a patient session."""
        patient_dir = self.db_root / patient_id
        if not patient_dir.exists():
            raise FileNotFoundError("Patient introuvable")
        drafts_dir = patient_dir / "_drafts"
        drafts_dir.mkdir(parents=True, exist_ok=True)
        draft_data = {
            "session_id": session_id,
            "patient_id": patient_id,
            "text_raw": text,
            "updated_at": datetime.utcnow().isoformat(),
        }
        with (drafts_dir / f"{session_id}.json").open("w", encoding="utf-8") as f:
            json.dump(draft_data, f, ensure_ascii=False, indent=2)

    def clear_draft(self, patient_id: str, session_id: str = "default") -> None:
        """Remove draft file for a patient session if present."""
        draft_path = self.db_root / patient_id / "_drafts" / f"{session_id}.json"
        if draft_path.exists():
            draft_path.unlink()
