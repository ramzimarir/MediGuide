"""main.py
Serveur FastAPI : Multi-Patients + Transcription + Neo4j/Qdrant Reasoning.
"""
import os
import logging
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

from shared.paths import DB_ROOT
from shared.patient_utils import backfill_note_timestamps
from routes import patients, notes, analysis

# --- CONFIGURATION ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mediguide_server")

app = FastAPI()
os.makedirs(DB_ROOT, exist_ok=True)

backfill_note_timestamps()

templates = Jinja2Templates(directory='frontend/templates')
app.mount("/static", StaticFiles(directory='frontend/static'), name="static")

# --- ROUTES ---
@app.get("/")
async def root(request: Request):
    """Page d'accueil - Interface MediGuide"""
    return templates.TemplateResponse("index.html", {"request": request})

# Include routers
app.include_router(patients.router)
app.include_router(notes.router)
app.include_router(analysis.router)

if __name__ == '__main__':
    uvicorn.run('main:app', host='0.0.0.0', port=8000, reload=True)