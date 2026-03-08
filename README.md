# MediGuide 🏥

> AI-powered medical prescription assistant combining speech recognition,
> vector retrieval, and medical knowledge graphs in a GraphRAG pipeline
> to support medication recommendations from patient consultation notes.

**Academic project** — M2 Artificial Intelligence & Data Science, UPEC Paris

![Interface Screenshot](docs/screenshot.png)

---

## What it does

A physician dictates or types a consultation note. The system:
1. Transcribes and structures the note into clinical sections
2. Extracts diagnoses, symptoms, and patient context
3. Runs hybrid retrieval: semantic disease matching in Qdrant + medical evidence from Neo4j
4. Fuses both retrieval sources into one GraphRAG context for the LLM report
5. Flags contraindications, interactions, and patient-specific warnings

---

## Pipeline Overview
```
Audio / Text Input
       │
       ▼
┌─────────────────┐
│    Ingestion     │  VAD → Transcription → Correction → NER Extraction
└────────┬────────┘
         │
         ▼
┌──────────────────────────────────────────────┐
│           GraphRAG Retrieval Layer           │
│ HybridRetriever: Qdrant Vector + Neo4j Graph │
└──────────────────────┬───────────────────────┘
        │
        ▼
┌─────────────────┐
│  Fused Context  │  Combined context injected into LLM prompt
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Recommendation  │  Medication Ranking → Contraindication Check → Report
└─────────────────┘
```

---

## GraphRAG Architecture

The retrieval stack is now hybrid by design:

1. `VectorSearchService` queries Qdrant for semantically similar disease candidates.
2. `DiseaseValidator` filters and normalizes disease matches against graph entities.
3. `Neo4jClient` retrieves medicine evidence (treats, substances, warnings, contraindications).
4. `HybridRetriever` fuses vector and graph outputs into one `combined_context`.
5. `PrescriptionPipeline` injects `combined_context` into the LLM report prompt.

This guarantees the LLM receives both semantic similarity evidence and structured medical graph knowledge in one grounded context block.

---

## Tech Stack

| Layer | Technology | Role |
|-------|-----------|------|
| API | FastAPI | REST endpoints |
| Speech | Groq Whisper | Audio transcription |
| LLM | Groq / EdenAI | Text correction, NER, report generation |
| Graph DB | Neo4j | Medical knowledge base |
| Vector DB | Qdrant | Semantic disease search |
| Retrieval | HybridRetriever | GraphRAG fusion (vector + graph) |
| Embeddings | Sentence Transformers | Disease vectorization |
| Frontend | Vanilla JS + Jinja2 | Web interface |
| Infrastructure | Docker Compose | Service orchestration |

---

## Project Structure
```
MediGuide/
├── routes/          # HTTP endpoints (patients, notes, analysis)
├── pipeline/        # Medical reasoning core (GraphRAG, validation, recommender)
│   └── hybrid_retriever.py  # Fuses vector and graph retrieval context for LLM
├── ingestion/       # Audio & text processing (VAD, transcription, NER)
├── storage/         # Data persistence (repositories, Neo4j client)
├── integrations/    # External API clients (Groq, EdenAI, embeddings)
├── shared/          # Config, models, logger, utilities
├── scripts/         # One-time DB setup scripts
└── frontend/        # HTML interface + JS client
```

---

## API Providers

This project uses **two different LLM providers** for different tasks:

| Provider | Used for | Config key |
|----------|----------|------------|
| **Groq** | Audio transcription (Whisper) + text correction | `GROQ_API_KEY` |
| **EdenAI** | Ontology mapping + warning professionalization | `EDENAI_API_KEY` + `EDENAI_MODEL` |

### Switching providers

Both clients are isolated in `integrations/`:

- To swap Groq → edit `ingestion/transcriber.py` and `ingestion/text_processor.py`
- To swap EdenAI → edit `integrations/edenai_client.py`, the interface 
  exposes `call_llm()` and `call_llm_json()` — replace the HTTP call 
  with any provider that returns plain text

The rest of the codebase is provider-agnostic.

---

## Data Notice

> ⚠️ **Medical data is not included in this repository.**

The knowledge base (`medicines_unified.json` and `disease_embeddings.json`) 
is built from **Vidal** — a proprietary French medical database. 
Redistributing this data is not permitted.

To use this project you need to:
1. Obtain your own medicine dataset in the same JSON format
2. Run the import scripts to populate Neo4j and Qdrant:
```bash
python scripts/load_medicines.py       # populates Neo4j
python scripts/load_embeddings.py      # populates Qdrant (disease vectors)
python scripts/load_conditions.py      # populates Qdrant (condition index)
```

The expected JSON structure for medicines is documented 
in `scripts/load_medicines.py`.

---

## Getting Started

### Prerequisites
- Docker & Docker Compose
- Python 3.10+
- Groq API key → [console.groq.com](https://console.groq.com)
- EdenAI API key → [app.edenai.run](https://app.edenai.run)

### 1. Clone and configure
```bash
git clone https://github.com/your-username/MediGuide.git
cd MediGuide
cp .env.example .env
# Fill in your API keys in .env
```

### 2. Start infrastructure
```bash
docker compose up -d
# Starts Neo4j (localhost:7474) and Qdrant (localhost:6333)
```

### 3. Load medical data
```bash
pip install -r requirements.txt
python scripts/load_medicines.py
python scripts/load_embeddings.py
python scripts/load_conditions.py
```

### 4. Run the app
```bash
uvicorn main:app --reload
# Open http://localhost:8000
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in your values:
```env
# Neo4j (pre-configured for Docker service)
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password

# Groq — transcription + text correction
GROQ_API_KEY=your_groq_api_key_here

# EdenAI — ontology mapping + report generation
EDENAI_API_KEY=your_edenai_api_key_here
EDENAI_MODEL=openai/gpt-4o

# Qdrant — vector search
QDRANT_URL=http://localhost:6333
```

---

## Project Status

Built as part of an M2 AI & Data Science project at UPEC Paris.  
Functional prototype — not intended for clinical use.

**Known limitations:**
- Patient data stored as local JSON files (no production-grade DB)
- No authentication on API endpoints
- Medical data requires a separate Vidal license

---

## Author

**Academic project**  
M2 Artificial Intelligence & Data Science, UPEC Paris

📫 [LinkedIn](https://www.linkedin.com/in/ramzi-marir-b6a08b38b) | [Email](mailto:ramzi.marir30@gmail.com)

---
