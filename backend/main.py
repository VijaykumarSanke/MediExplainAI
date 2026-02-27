"""
main.py – FastAPI Application Entry Point
==========================================
Architecture Role: Layer 1 – PDF Upload Layer / API Gateway
Responsibility:
    - Expose REST API endpoints for the frontend
    - Orchestrate parser → risk engine → LLM agent pipeline
    - Handle errors gracefully with informative responses
    - Enable CORS for local frontend development

Endpoints:
    GET  /health          → Health check
    POST /upload          → Parse PDF, return extracted table
    POST /analyze         → Full analysis: risk score + AI summary
    POST /ask             → Q&A agent for interactive questions
"""

import os
import io
import logging
from contextlib import asynccontextmanager
from dotenv import load_dotenv

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Load environment variables from .env file (if present)
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy-loaded singletons (initialised at startup to avoid cold-start delay)
# ---------------------------------------------------------------------------
_rag_pipeline = None
_llm_agent = None
_risk_engine = None


def get_rag():
    global _rag_pipeline
    if _rag_pipeline is None:
        from rag_pipeline import RAGPipeline
        logger.info("Initialising RAG pipeline…")
        _rag_pipeline = RAGPipeline()
    return _rag_pipeline


def get_llm():
    global _llm_agent
    if _llm_agent is None:
        from llm_agent import LLMAgent
        logger.info("Initialising LLM agent…")
        _llm_agent = LLMAgent(get_rag())
    return _llm_agent


def get_risk_engine():
    global _risk_engine
    if _risk_engine is None:
        from risk_engine import RiskEngine
        logger.info("Initialising Risk Engine…")
        _risk_engine = RiskEngine()
    return _risk_engine


# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-warm singletons at startup."""
    logger.info("Starting Lab Report Intelligence Agent API…")
    try:
        get_risk_engine()
        get_rag()
        get_llm()
        logger.info("All components initialised successfully.")
    except Exception as exc:
        logger.warning("Startup pre-warming failed (non-fatal): %s", exc)
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title="Lab Report Intelligence Agent API",
    description="AI-Powered Patient Report Simplifier – Hackathon Prototype",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS – allow all origins for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files will be mounted at the end to avoid intercepting API routes


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------

class AskRequest(BaseModel):
    question: str
    report_context: str = ""


class AnalyseRequest(BaseModel):
    """Body includes the previously uploaded and extracted lab data."""
    tests: list[dict]  # list of {test_name, measured_value, unit, reference_range}
    historical_tests: list[dict] = None  # optional list of older tests for trend comparison


# ---------------------------------------------------------------------------
# Helper: Convert TestResult dataclass to dict for JSON serialisation
# ---------------------------------------------------------------------------

def _result_to_dict(r) -> dict:
    return {
        "test_name": r.test_name,
        "measured_value": r.measured_value,
        "unit": r.unit,
        "reference_range": r.reference_range,
        "status": r.status,
        "normal_min": r.normal_min,
        "normal_max": r.normal_max,
        "description": r.description,
        "status_description": r.status_description,
        "in_benchmark": r.in_benchmark,
        "is_critical": getattr(r, "is_critical", False),
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "Lab Report Intelligence Agent"}


@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    """
    Layer 1 + Layer 2: Accept a PDF upload and extract lab values.
    
    Returns extracted lab test rows as a JSON array.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are accepted. Please upload a .pdf file.",
        )

    try:
        contents = await file.read()
        if len(contents) == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        from parser import parse_pdf
        df = parse_pdf(io.BytesIO(contents))

        if df.empty:
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": (
                        "The PDF was read, but no lab test values could be extracted. "
                        "The report may use a format that requires manual review."
                    ),
                    "tests": [],
                    "count": 0,
                },
            )

        tests = df.to_dict(orient="records")
        logger.info("Extracted %d tests from uploaded PDF '%s'.", len(tests), file.filename)

        return {
            "success": True,
            "message": f"Successfully extracted {len(tests)} lab test(s).",
            "tests": tests,
            "count": len(tests),
        }

    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.error("PDF upload failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="An error occurred while processing the PDF. Please try again.",
        )


@app.post("/analyze")
async def analyze_report(request: AnalyseRequest):
    """
    Layers 3–6: Full analysis pipeline.
    
    Accepts extracted test data, runs risk engine, and generates AI summary.
    Returns: risk score, risk category, full results, patterns, AI summary.
    """
    if not request.tests:
        raise HTTPException(
            status_code=400,
            detail="No test data provided. Please upload a PDF first.",
        )

    try:
        import pandas as pd
        df = pd.DataFrame(request.tests)
        
        historical_df = None
        if request.historical_tests:
            historical_df = pd.DataFrame(request.historical_tests)

        # Layer 3 + 4: Risk engine
        engine = get_risk_engine()
        report = engine.analyse(df, historical_df=historical_df)

        # Prepare structured results
        results_list = [_result_to_dict(r) for r in report.results]

        # Layer 6: AI Summary
        agent = get_llm()
        summary = agent.generate_summary(
            results=report.results,
            risk_score=report.risk_score,
            risk_category=report.risk_category,
            patterns=report.patterns,
            trends=report.trends,
        )

        return {
            "success": True,
            "risk_score": report.risk_score,
            "risk_category": report.risk_category,
            "abnormal_count": report.abnormal_count,
            "total_count": len(results_list),
            "results": results_list,
            "patterns": report.patterns,
            "trends": report.trends,
            "ai_summary": summary,
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Analysis failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {str(exc)}",
        )


@app.post("/ask")
async def ask_question(request: AskRequest):
    """
    Layer 7: Interactive Q&A Agent.
    
    Answers patient questions about their lab report using RAG.
    Strictly limited to knowledge base — no hallucinations.
    """
    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    if len(request.question) > 500:
        raise HTTPException(
            status_code=400,
            detail="Question is too long. Please keep it under 500 characters.",
        )

    try:
        agent = get_llm()
        answer = agent.answer_question(
            question=request.question.strip(),
            report_context=request.report_context,
        )
        return {
            "success": True,
            "question": request.question,
            "answer": answer,
        }
    except Exception as exc:
        logger.error("Q&A failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="Could not generate an answer. Please try again.",
        )


# ---------------------------------------------------------------------------
# Mount frontend static files last
# ---------------------------------------------------------------------------
frontend_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")
if os.path.exists(frontend_path):
    # html=True allows serving index.html on /
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")


# ---------------------------------------------------------------------------
# Dev entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
