from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict
import json
import shutil

from shared.paths import DB_ROOT


class PatientSummary(TypedDict):
    id: str
    name: str


class NoteRecord(TypedDict):
    id: Optional[str]
    text: Optional[str]
    text_raw: str
    text_clean: str
    dimension: int
    timestamp: Optional[str]
    title: Optional[str]


class PatientNotFoundError(Exception):
    """Raised when a patient directory does not exist."""
    pass


class PatientInfoNotFoundError(Exception):
    """Raised when patient_info.json is missing."""
    pass


class PatientRepositoryError(Exception):
    """Raised when patient repository operations fail."""
    pass


class PatientRepository:
    """Manages patient metadata and note records in local JSON storage."""
    def __init__(self, db_root: Path = DB_ROOT) -> None:
        """Initialize repository with storage root path."""
        self.db_root = Path(db_root)

    def list_patients(self) -> List[PatientSummary]:
        """List all patient folders with display names."""
        try:
            patients: List[PatientSummary] = []
            if not self.db_root.exists():
                return patients
            for entry in self.db_root.iterdir():
                if not entry.is_dir():
                    continue
                info_path = entry / "patient_info.json"
                name = entry.name
                if info_path.exists():
                    try:
                        with info_path.open("r", encoding="utf-8") as f:
                            data = json.load(f)
                        name = data.get("name", entry.name)
                    except Exception:
                        pass
                patients.append({"id": entry.name, "name": name})
            return patients
        except Exception as e:
            raise PatientRepositoryError(f"Erreur lecture patients: {e}") from e

    def create_patient(self, folder_id: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create patient folder and persist initial metadata."""
        try:
            folder_path = self.db_root / folder_id
            folder_path.mkdir(parents=True, exist_ok=True)
            with (folder_path / "patient_info.json").open("w", encoding="utf-8") as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            return metadata
        except Exception as e:
            raise PatientRepositoryError(f"Erreur creation patient: {e}") from e

    def load_patient_info(self, patient_id: str) -> Dict[str, Any]:
        """Load full patient_info.json for a given patient ID."""
        try:
            patient_info_path = self.db_root / patient_id / "patient_info.json"
            if not patient_info_path.exists():
                raise PatientInfoNotFoundError("Patient introuvable")
            with patient_info_path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except PatientInfoNotFoundError:
            raise
        except Exception as e:
            raise PatientRepositoryError(f"Erreur lecture patient_info.json: {e}") from e

    def update_patient_info(self, patient_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Merge update fields into patient_info.json and return the result."""
        try:
            patient_info_path = self.db_root / patient_id / "patient_info.json"
            if not patient_info_path.exists():
                raise PatientInfoNotFoundError("Patient introuvable")
            with patient_info_path.open("r", encoding="utf-8") as f:
                existing_data = json.load(f)
            existing_data.update(updates)
            with patient_info_path.open("w", encoding="utf-8") as f:
                json.dump(existing_data, f, ensure_ascii=False, indent=2)
            return existing_data
        except PatientInfoNotFoundError:
            raise
        except Exception as e:
            raise PatientRepositoryError(f"Erreur update patient_info.json: {e}") from e

    def delete_patient(self, patient_id: str) -> None:
        """Delete patient directory and all associated files."""
        try:
            patient_dir = self.db_root / patient_id
            if not patient_dir.exists():
                raise PatientNotFoundError("Patient introuvable")
            shutil.rmtree(patient_dir)
        except PatientNotFoundError:
            raise
        except Exception as e:
            raise PatientRepositoryError(f"Erreur suppression patient: {e}") from e

    def load_patient_notes(self, patient_id: str) -> List[NoteRecord]:
        """Load all note records for a patient, sorted by timestamp desc."""
        try:
            patient_dir = self.db_root / patient_id
            if not patient_dir.exists():
                raise PatientNotFoundError("Patient introuvable")
            recordings: List[NoteRecord] = []
            for file_path in patient_dir.iterdir():
                if file_path.suffix != ".json" or file_path.name == "patient_info.json":
                    continue
                try:
                    with file_path.open("r", encoding="utf-8") as f:
                        data = json.load(f)
                    recordings.append(
                        {
                            "id": data.get("id"),
                            "text": data.get("text"),
                            "text_raw": data.get("text_raw", ""),
                            "text_clean": data.get("text_clean", ""),
                            "dimension": data.get("dimension", 0),
                            "timestamp": data.get("timestamp"),
                            "title": data.get("title", None),
                        }
                    )
                except Exception:
                    pass
            recordings.sort(key=lambda x: str(x.get("timestamp", "")), reverse=True)
            return recordings
        except PatientNotFoundError:
            raise
        except Exception as e:
            raise PatientRepositoryError(f"Erreur lecture historique patient: {e}") from e

    def load_note_by_id(self, patient_id: str, note_id: str) -> Optional[Dict[str, Any]]:
        """Load one note JSON by patient and note ID."""
        try:
            path = self.db_root / patient_id / f"{note_id}.json"
            if not path.exists():
                return None
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            raise PatientRepositoryError(f"Erreur lecture note {note_id}: {e}") from e
