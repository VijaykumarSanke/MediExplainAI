# MediExplainAI – Lab Report Explainer

MediExplainAI turns a lab-report PDF into a plain-language explanation. It extracts test values from the PDF, compares them with reference benchmarks using a rule-based risk engine, and uses a retrieval-augmented LLM (RAG) to explain the results and answer follow-up questions in 12 languages.

> **Disclaimer:** This project is for education only. It does not diagnose and is not medical advice. Always consult a doctor.

## Features

- **PDF parsing** – extracts lab values with `pdfplumber` and regex, with a table-extraction fallback. An alias dictionary normalizes test names (for example "Hb" and "Hgb" both map to Hemoglobin).
- **Rule-based risk engine** – compares each value with the benchmark ranges in `benchmark.json` (11 tests), marks it Low, Normal or High, and computes a weighted risk score and category (Stable, Monitor, Moderate Concern, Elevated Risk).
- **Pattern detection** – flags simple correlation patterns (for example anemia, cardiovascular) defined in the benchmark file.
- **Trend comparison** – upload a previous report to see how values changed.
- **RAG pipeline** – medical education text is chunked, embedded with `BAAI/bge-small-en`, and stored in a FAISS index. The top matching chunks are added to the LLM prompt.
- **LLM explanations and Q&A** – Groq-hosted Llama 3.3 70B writes the summary and answers questions, with safety prompts and a disclaimer on every response. A rule-based fallback summary is used if the LLM is unavailable.
- **12 languages** – English, Hindi, Telugu, Tamil, Kannada, Bengali, Marathi, Spanish, French, Portuguese, Arabic and Chinese (Simplified).
- **Accounts and history** – JWT authentication (bcrypt password hashing). Logged-in users get a saved history of their analyzed reports.
- **Web UI** – vanilla JavaScript frontend with drag-and-drop upload, results table, risk gauge, AI summary and chat.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, FastAPI, Uvicorn |
| PDF / data | pdfplumber, Pandas |
| AI | LangChain, Groq (Llama 3.3 70B), sentence-transformers (`BAAI/bge-small-en`), FAISS |
| Auth / DB | JWT (python-jose), passlib + bcrypt, SQLAlchemy, SQLite |
| Frontend | HTML, CSS, JavaScript |

## Architecture

```
PDF upload → parser.py (pdfplumber + regex)
          → risk_engine.py (benchmark.json → risk score, patterns, trends)
          → rag_pipeline.py (FAISS retrieval)
          → llm_agent.py (Groq Llama 3.3 → summary / Q&A)
          → frontend (results, gauge, chat, history)
```

## Project Structure

```
MediExplainAI/
├── backend/
│   ├── main.py            # FastAPI app and endpoints
│   ├── parser.py          # PDF parsing + test-name aliases
│   ├── risk_engine.py     # Benchmark comparison, scoring, patterns, trends
│   ├── benchmark.json     # 11 supported lab tests + correlation rules
│   ├── rag_pipeline.py    # Chunking, embeddings, FAISS retrieval
│   ├── llm_agent.py       # Prompts, Groq LLM, multilingual output
│   ├── auth.py            # Register / login / JWT
│   ├── models.py          # SQLAlchemy models (User, ReportHistory)
│   ├── database.py        # DB session setup
│   ├── requirements.txt
│   └── .env.example
├── frontend/              # index.html, auth.html, script.js, style.css
├── tests/test_analyze.py  # Manual API request script
└── PROJECT_ARCHITECTURE.md
```

## Getting Started

1. Clone the repository and go to the backend folder:
   ```bash
   git clone https://github.com/VijaykumarSanke/MediExplainAI.git
   cd MediExplainAI/backend
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create your environment file and fill in the values:
   ```bash
   cp .env.example .env
   ```
   - `GROQ_API_KEY` – get one at https://console.groq.com/keys
   - `JWT_SECRET` – use a long random string
4. Run the server:
   ```bash
   python main.py
   ```
   or `uvicorn main:app --reload --port 8000`.
5. Open http://localhost:8000. Interactive API docs are at http://localhost:8000/docs.

The first start builds the FAISS index and may download the embedding model, so it can take a little while.

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/upload` | Upload a PDF and get the extracted lab values |
| POST | `/analyze` | Risk score, patterns, trends and AI summary (saved to history if logged in) |
| POST | `/ask` | Ask a question about the report |
| POST | `/auth/register` | Create an account |
| POST | `/auth/login` | Log in and receive a JWT |
| GET | `/auth/me` | Current user profile |
| GET | `/history` | List saved reports (auth required) |
| GET / DELETE | `/history/{id}` | View or delete a saved report (auth required) |

## Limitations

- Only the 11 tests in `benchmark.json` have built-in reference data. Other tests fall back to the reference range printed in the PDF.
- Parsing uses regex and table extraction, so unusual report layouts may not be read correctly.
- The risk score comes from simple weighted rules, not a trained model.
- Tests are limited to a manual request script; automated tests are planned.
- Logged-in users' analysis results are stored in the local database. This project is not HIPAA-compliant.

## Future Improvements

- Automated tests (parser and risk engine) and a CI workflow
- Support for more lab tests and report layouts
- Deployment with a hosted demo

## Author

Sanke Vijaykumar – [GitHub](https://github.com/VijaykumarSanke) · vijaykumar.sanke7@gmail.com
