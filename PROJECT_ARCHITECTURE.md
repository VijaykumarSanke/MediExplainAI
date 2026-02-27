# Lab Report Intelligence Agent – Comprehensive Project Documentation

This document provides a detailed explanation of the architecture, technologies, and logic used in the **Lab Report Intelligence Agent** (AI-Powered Patient Report Simplifier).

---

## 1. Project Overview
The **Lab Report Intelligence Agent** is a healthcare AI tool designed to bridge the communication gap between clinical lab reports and patient understanding. It transforms complex medical data (PDFs) into clear, reassuring, and patient-safe education using Retrieval-Augmented Generation (RAG) and specialized medical rule engines.

### Key Objectives
*   **Safety First:** Never diagnose. Always educate and encourage doctor consultation.
*   **Accessibility:** Use simple, warm, and conversational language (the "caring friend" tone).
*   **Accuracy:** Use a curated medical benchmark database for initial analysis.

---

## 2. Tech Stack Selection (Why these?)

### Backend
*   **FastAPI:** Selected for its high performance, native async support, and automatic documentation (Swagger UI).
*   **pdfplumber:** Used for robust text extraction from PDF documents, handling multi-column layouts better than basic libraries like PyPDF2.
*   **Pandas:** The industry standard for data manipulation, used here to structure extracted lab values for easy analysis.
*   **FAISS (Facebook AI Similarity Search):** A high-performance vector database used to store and retrieve medical education chunks.

### AI & LLM
*   **Groq (Llama 3.3 70B):** Provides ultra-fast inference for the LLM. Llama 3.3 (70B) was chosen for its high reasoning capabilities while remaining free on the Groq tier.
*   **HuggingFace Embeddings (`BAAI/bge-small-en`):** A small but powerful open-source embedding model that runs locally on CPU, eliminating the need for paid OpenAI embedding credits.

### Frontend
*   **Vanilla JS (ES6+):** Purposefully chosen over React/Vue to keep the project lightweight, high-performance, and "hackathon-ready" without build-tool overhead.
*   **Vanilla CSS:** Custom design system built with CSS variables to ensure a sleek, premium, "patient-safe" aesthetic (soft shadows, rounded cards, medical-safe color palette).

---

## 3. The 6-Layer Architecture

The project follows a modular 6-layer architecture to ensure scalability and maintainability.

### Layer 1: Ingestion (API)
*   **File:** `main.py`
*   **Logic:** Receives the PDF through a POST request, manages the lifecycle of the other layers, and handles CORS and error responses.

### Layer 2: PDF Parsing
*   **File:** `parser.py`
*   **Logic:** Uses regex patterns and `pdfplumber` to sweep through raw text. It includes a massive list of **Test Aliases** (e.g., "Hb" -> "Hemoglobin") to ensure that different naming conventions in various hospitals all map to the same internal keys.

### Layer 3: Benchmark Comparison (Rule Engine)
*   **File:** `risk_engine.py` + `benchmark.json`
*   **Logic:** 
    *   **Fuzzy Matching:** If an exact name match fails, it tries substring matching and keyword overlap to find the right test in the database.
    *   **PDF Fallback:** If a test isn't in our database, the engine "reads" the reference range printed on the PDF itself to determine if the value is High, Low, or Normal.

### Layer 4: Risk Scoring
*   **File:** `risk_engine.py`
*   **Logic:** Assigns weights to abnormal results. A high LDL (cholesterol) might add more "risk weight" than a slightly high Platelet count. It then maps the total score to categories like "Stable", "Monitor", or "Moderate Concern".

### Layer 5: RAG Pipeline (Knowledge Retrieval)
*   **File:** `rag_pipeline.py`
*   **Logic:** 
    *   **Indexing:** Chunks the `benchmark.json` and `knowledge_base/` text into small pieces.
    *   **Retrieval:** When a user asks a question, the agent finds the 3 most relevant "medical facts" from the local index to feed into the AI's prompt. This prevents "hallucinations" (AI making things up).

### Layer 6: Interaction (LLM Agent)
*   **File:** `llm_agent.py`
*   **Logic:** 
    *   **Safety Prompts:** Implements a strict "System Prompt" that forbids self-diagnosis and enforces a warm tone.
    *   **Markdown Formatting:** Generates structured Markdown (bolding, lists, horizontal rules) which the frontend then renders into beautiful HTML.

---

## 4. Design & UX Decisions

### Patient-Safe UI
*   **Colors:** We avoided alarming "Neon Red". Instead, we use soft ambers (`#F59E0B`) and calm greens (`#10B981`) to reduce patient anxiety.
*   **Gradient Header:** Uses a premium blue gradient (`#1E40AF` to `#3B82F6`) to convey medical professionalism and trust.
*   **Risk Gauge:** A visual progress bar helps patients instantly see where they stand without reading a single number.

### AI Communication Style
*   **concise but helpful:** The prompts are tuned to provide enough detail (what the test is, why it matters, lifestyle tip) while staying under a readable length.
*   **No Emojis circles:** While we use ✅📈📉 sparingly, we removed the colored circle emojis (🔴🟡🟢) from the AI summary text to keep the interface professional and focused on words.

---

## 5. File-by-File Guide

### Backend (`/backend`)

*   **`main.py`**  
    The "Brain" of the operation. This is the FastAPI entry point. It handles the web server setup, defines the three main API endpoints (`/upload`, `/analyze`, `/ask`), and orchestrates the flow of data between the parser, the risk engine, and the AI agent.

*   **`parser.py`**  
    The "Extractor". It uses the `pdfplumber` library to read raw text from uploaded PDFs. Its secret weapon is a massive dictionary of **Medical Aliases** that ensures "Hb", "Hemoglobin", and "Hgb" are all understood as the same thing.

*   **`risk_engine.py`**  
    The "Medical Logician". This file compares the numbers extracted from the PDF against the `benchmark.json` database. It handles the fuzzy matching logic (so "Platelet Count" matches "Platelets") and the fallback logic (reading reference ranges directly from the PDF if a test is unknown).

*   **`llm_agent.py`**  
    The "Translator". This file connects to Groq's Llama 3.3 model. It contains the "System Prompts" that command the AI to act like a caring friend, avoid medical diagnoses, and format everything into clean, readable Markdown for the patient.

*   **`rag_pipeline.py`**  
    The "Research Librarian". It handles Retrieval-Augmented Generation (RAG). It takes the medical education text and turns it into "vectors" (numbers) using HuggingFace. When a patient asks a question, this file finds the matching medical facts to ensure the AI's answer is based on data, not guesses.

*   **`benchmark.json`**  
    The "Knowledge Source". This is our internal medical database. It contains the normal ranges, risk weights, and educational descriptions for the 8 core lab tests we support, plus "correlation patterns" like identifying Anemia.

*   **`requirements.txt`**  
    The "Grocery List". It lists every Python library needed to run the project, including versions for `fastapi`, `langchain-groq`, and `faiss-cpu`.

*   **`.env` & `.env.example`**  
    The "Key Vault". These store your sensitive API keys (like the Groq key) so they aren't hardcoded into the scripts.

---

### Frontend (`/frontend`)

*   **`index.html`**  
    The "Skeleton". Defines the 6 sections of the GUI: the upload zone, the results table, the risk gauge, the AI summary area, and the interactive chat window.

*   **`style.css`**  
    The "Skin". Contains the premium design system. It uses modern CSS techniques like gradients, glassmorphism-lite badges, and responsive layouts to make the medical data look non-intimidating and clean.

*   **`script.js`**  
    The "Nerves". This handles all front-end interactivity. It manages the drag-and-drop file upload, calls the API endpoints, updates the UI elements dynamically, and includes a **Markdown-to-HTML parser** so the AI's bold text and lists look great.

---

---

## 6. Security & Safety Mechanisms
1.  **Strict Prompting:** The AI is repeatedly told NOT to diagnose.
2.  **Disclaimer Injection:** Every AI response is automatically wrapped with a legal medical disclaimer.
3.  **Local RAG:** Medical education is pulled from a verified internal knowledge base, not just the general internet.
4.  **No PHI Storage:** The system parses records in real-time. (In a production environment, we would add further HIPAA-compliant data handling).

---
**Document Version:** 1.2  
**Updated:** February 2026
