"""
rag_pipeline.py – Retrieval-Augmented Generation (RAG) Layer
=============================================================
Architecture Role: Layer 5 – RAG Layer
Responsibility:
    - Build a knowledge base from benchmark descriptions + educational content
    - Chunk and embed documents using OpenAI text-embedding-3-small
      (falls back to BAAI/bge-small-en via sentence-transformers if no API key)
    - Store embeddings in a FAISS vector store (persisted to disk)
    - Expose retrieve(query, k) to pull relevant context for LLM prompts
"""

import os
import json
import logging
from pathlib import Path

from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS

logger = logging.getLogger(__name__)

# Paths
_BENCHMARK_PATH = Path(__file__).parent / "benchmark.json"
_FAISS_INDEX_PATH = Path(__file__).parent / "faiss_index"


def _get_embeddings():
    """
    Return the appropriate embedding model.
    - Uses BAAI/bge-small-en (HuggingFace) for free embeddings.
    """
    logger.info("Using HuggingFace BAAI/bge-small-en for embeddings.")
    from langchain_community.embeddings import HuggingFaceEmbeddings
    return HuggingFaceEmbeddings(model_name="BAAI/bge-small-en")


def _build_knowledge_base() -> list[Document]:
    """
    Construct the RAG knowledge base from:
    1. benchmark.json educational texts per test
    2. General WHO-style educational documents
    3. Disclaimer and safety guidelines
    """
    documents = []

    # --- Source 1: Benchmark educational texts ---
    with open(_BENCHMARK_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    for test_name, info in data.get("tests", {}).items():
        edu_text = info.get("educational_text", "")
        if edu_text:
            documents.append(
                Document(
                    page_content=edu_text,
                    metadata={"source": "benchmark", "test": test_name},
                )
            )

    # --- Source 2: General WHO-style health education ---
    general_texts = [
        (
            "complete_blood_count",
            """A Complete Blood Count (CBC) is one of the most common blood tests ordered by healthcare 
providers. It measures several components of blood including red blood cells, white blood cells, 
hemoglobin, hematocrit, and platelets. The CBC provides a general overview of overall health and 
can help detect a wide range of conditions including anemia, infections, and certain blood diseases. 
Results must always be interpreted by a qualified healthcare professional in the context of the 
patient's full clinical picture.""",
        ),
        (
            "cholesterol_overview",
            """Cholesterol is a fatty substance found in the blood. While the body needs cholesterol to 
build healthy cells, high levels of certain types of cholesterol can increase the risk of heart 
disease over time. There are two main types: LDL (low-density lipoprotein), often called 'bad' 
cholesterol, and HDL (high-density lipoprotein), often called 'good' cholesterol. A lipid panel 
blood test measures total cholesterol, LDL, HDL, and triglycerides. Diet, physical activity, and 
genetics all play roles in cholesterol levels. Always work with a healthcare professional to 
understand your cholesterol results.""",
        ),
        (
            "blood_glucose_overview",
            """Blood glucose (blood sugar) testing is used to check the amount of glucose in the blood. 
Glucose is the main source of energy for the body's cells and comes primarily from the foods we eat. 
Fasting blood glucose tests are typically performed after not eating for at least 8 hours. Consistently 
elevated fasting blood glucose levels may be associated with prediabetes or diabetes. Managing blood 
glucose involves a combination of diet, exercise, and in some cases medication prescribed by a doctor. 
Lab results should always be reviewed with a healthcare professional.""",
        ),
        (
            "kidney_function_overview",
            """The kidneys are vital organs that filter waste products from the blood and regulate fluid 
balance. Kidney function is often assessed through blood tests measuring creatinine and blood urea 
nitrogen (BUN), as well as urine tests. Creatinine is a waste product of muscle metabolism, and 
healthy kidneys remove it from the blood efficiently. Elevated creatinine may indicate reduced 
kidney filtering capacity. Factors like hydration status, muscle mass, medications, and diet can 
influence creatinine readings. Kidney function results should always be interpreted by a 
qualified healthcare professional.""",
        ),
        (
            "healthy_lifestyle_general",
            """General lifestyle factors that support overall health include: maintaining a balanced diet 
rich in vegetables, fruits, whole grains, and lean proteins; engaging in regular physical activity 
(at least 150 minutes of moderate exercise per week as per WHO recommendations); getting adequate 
sleep (7–9 hours per night for adults); staying well-hydrated by drinking sufficient water; avoiding 
smoking; and limiting alcohol consumption. These are general wellness guidelines. Individual health 
needs vary, and personal health decisions should always be discussed with a qualified healthcare 
provider.""",
        ),
        (
            "understanding_reference_ranges",
            """Reference ranges in lab reports represent values that are typically observed in a healthy 
population. They are statistical guides, not absolute thresholds. A value slightly outside the 
reference range does not automatically mean something is wrong — many factors including age, sex, 
pregnancy, medications, and lab-specific calibration affect what a 'normal' range looks like for an 
individual. Similarly, a value within the reference range does not guarantee perfect health. Reference 
ranges are best understood as one piece of information that a healthcare professional uses, alongside 
symptoms, physical examination, and medical history, to form an overall picture of health.""",
        ),
        (
            "disclaimer_and_safety",
            """IMPORTANT DISCLAIMER: The information provided by this system is for educational purposes 
only. It is NOT intended as medical advice, diagnosis, or treatment. Lab report interpretations 
provided here are general educational summaries based on reference ranges and should NOT be used 
to make any health decisions. Always consult a qualified and licensed healthcare professional, such 
as a doctor or specialist, for interpretation of your lab results and for any medical advice. If you 
are experiencing a medical emergency, please contact emergency services immediately. This tool is 
designed to help you understand general concepts related to your lab report — it is not a substitute 
for professional medical care.""",
        ),
    ]

    for doc_id, text in general_texts:
        documents.append(
            Document(
                page_content=text.strip(),
                metadata={"source": "general_education", "topic": doc_id},
            )
        )

    logger.info("Built knowledge base with %d raw documents.", len(documents))
    return documents


def _chunk_documents(documents: list[Document]) -> list[Document]:
    """Chunk documents into smaller pieces for embedding."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=["\n\n", "\n", ".", " "],
    )
    chunks = splitter.split_documents(documents)
    logger.info("Chunked into %d pieces for embedding.", len(chunks))
    return chunks


class RAGPipeline:
    """
    Manages the full RAG lifecycle:
    - Build/load FAISS vector store
    - Retrieve top-k relevant chunks for a given query
    """

    def __init__(self):
        self.embeddings = _get_embeddings()
        self.vectorstore = self._load_or_build_index()

    def _load_or_build_index(self) -> FAISS:
        """Load a persisted FAISS index or build and save a new one."""
        if _FAISS_INDEX_PATH.exists():
            logger.info("Loading existing FAISS index from %s", _FAISS_INDEX_PATH)
            try:
                return FAISS.load_local(
                    str(_FAISS_INDEX_PATH),
                    self.embeddings,
                    allow_dangerous_deserialization=True,
                )
            except Exception as exc:
                logger.warning("Failed to load FAISS index (%s). Rebuilding.", exc)

        logger.info("Building new FAISS index…")
        documents = _build_knowledge_base()
        chunks = _chunk_documents(documents)
        vectorstore = FAISS.from_documents(chunks, self.embeddings)
        vectorstore.save_local(str(_FAISS_INDEX_PATH))
        logger.info("FAISS index saved to %s", _FAISS_INDEX_PATH)
        return vectorstore

    def retrieve(self, query: str, k: int = 4) -> str:
        """
        Retrieve top-k relevant chunks from the knowledge base.

        Parameters
        ----------
        query : str
            The question or topic to search for.
        k : int
            Number of top chunks to retrieve.

        Returns
        -------
        str
            Concatenated text of retrieved chunks, separated by newlines.
        """
        try:
            docs = self.vectorstore.similarity_search(query, k=k)
            context_parts = [doc.page_content for doc in docs]
            return "\n\n".join(context_parts)
        except Exception as exc:
            logger.error("RAG retrieval failed: %s", exc)
            return "General reference information is temporarily unavailable."

    def rebuild_index(self):
        """Force-rebuild the FAISS index (useful after updating benchmark.json)."""
        logger.info("Force-rebuilding FAISS index…")
        documents = _build_knowledge_base()
        chunks = _chunk_documents(documents)
        self.vectorstore = FAISS.from_documents(chunks, self.embeddings)
        self.vectorstore.save_local(str(_FAISS_INDEX_PATH))
        logger.info("FAISS index rebuilt and saved.")
