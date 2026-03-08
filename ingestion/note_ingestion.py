from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
import os
import shutil
import tempfile
import uuid

from groq import Groq

from ingestion import vad as vad_module
from ingestion import transcriber
from ingestion import llm_extractor
from ingestion.note_summary import summarize_note
from shared.paths import DB_ROOT
from storage.note_repository import NoteRepository
from ingestion.text_processor import correct_text_with_groq


class NoteIngestionService:
    """Handles patient note ingestion from audio files or text inputs."""
    def __init__(
        self,
        db_root: Path = DB_ROOT,
        groq_client: Optional[Groq] = None,
        note_repository: Optional[NoteRepository] = None,
    ) -> None:
        """Initialize the ingestion service with database and repository paths."""
        self.db_root = Path(db_root)
        self.groq_client = groq_client
        self.note_repository = note_repository or NoteRepository(self.db_root)

    def transcribe_audio(self, audio_file, patient_id: str) -> Dict[str, Any]:
        """Convert audio file to processed medical text. Returns raw, cleaned, and filtered text."""
        patient_dir = self.db_root / patient_id
        if not patient_dir.exists():
            raise FileNotFoundError("Patient not found")
        if not getattr(audio_file, "filename", None):
            raise ValueError("No filename")

        record_id = str(uuid.uuid4())
        with tempfile.TemporaryDirectory() as tmpdir:
            ext = os.path.splitext(audio_file.filename)[1]
            input_path = os.path.join(tmpdir, f"input{ext}")
            with open(input_path, "wb") as fh:
                shutil.copyfileobj(audio_file.file, fh)

            from pydub import AudioSegment
            audio = AudioSegment.from_file(input_path).set_frame_rate(16000).set_channels(1).set_sample_width(2)
            wav_path = os.path.join(tmpdir, "norm.wav")
            audio.export(wav_path, format="wav")

            try:
                filtered_path, _ = vad_module.apply_vad(wav_path, output_dir=tmpdir)
            except Exception:
                filtered_path = wav_path

            raw_text = transcriber.transcribe(filtered_path, language="fr")
            clean_text = correct_text_with_groq(raw_text)
            filtered_text = llm_extractor.process_text(clean_text)

            ts = datetime.utcnow().isoformat()
            rec_data = {
                "id": record_id,
                "patient_id": patient_id,
                "text_raw": raw_text,
                "text_clean": clean_text,
                "text": filtered_text,
                "embedding": [],
                "dimension": 0,
                "timestamp": ts,
                "title": "Note ",
            }
            self.note_repository.save_note(patient_id, rec_data)

            return {
                "id": record_id,
                "text_raw": raw_text,
                "text_clean": clean_text,
                "text_filtered": filtered_text,
                "dimension": 0,
                "title": "Note ",
                "timestamp": ts,
            }

    def transcribe_text(self, raw_text: str, patient_id: str, title: Optional[str] = None) -> Dict[str, Any]:
        """Process raw medical text and save as a note. Returns cleaned and filtered text."""
        if not raw_text or not raw_text.strip():
            raise ValueError("Text is empty")
        if not (self.db_root / patient_id).exists():
            raise FileNotFoundError("Patient not found")

        record_id = str(uuid.uuid4())
        clean_text = correct_text_with_groq(raw_text)
        filtered_text = llm_extractor.process_text(clean_text)
        ts = datetime.utcnow().isoformat()

        rec_data = {
            "id": record_id,
            "patient_id": patient_id,
            "text_raw": raw_text,
            "text_clean": clean_text,
            "text": filtered_text,
            "embedding": [],
            "dimension": 0,
            "timestamp": ts,
            "title": title or "Note ",
        }
        self.note_repository.save_note(patient_id, rec_data)

        return {
            "id": record_id,
            "text_raw": raw_text,
            "text_clean": clean_text,
            "text_filtered": filtered_text,
            "dimension": 0,
            "title": title or "Note ",
            "timestamp": ts,
        }

    def save_draft(self, patient_id: str, text: str, session_id: str = "default") -> Dict[str, str]:
        """Save a draft note to the specified session."""
        if not (self.db_root / patient_id).exists():
            raise FileNotFoundError("Patient not found")
        self.note_repository.save_draft(patient_id, text or "", session_id=session_id)
        return {"status": "saved", "session_id": session_id}

    def clear_draft(self, patient_id: str, session_id: str = "default") -> Dict[str, str]:
        """Delete a draft session."""
        self.note_repository.clear_draft(patient_id, session_id=session_id)
        return {"status": "cleared", "session_id": session_id}

    def note_summary(self, text: str, timestamp: Optional[str] = None) -> Dict[str, Any]:
        """Generate a summary of the medical note."""
        if not text:
            raise ValueError("Text is empty")
        return summarize_note(text, timestamp, client=self.groq_client)

    def delete_note_by_item_id(self, item_id: str) -> Dict[str, str]:
        """Delete a note by its ID."""
        deleted_id = self.note_repository.delete_note_by_item_id(item_id)
        return {"status": "deleted", "id": deleted_id}
