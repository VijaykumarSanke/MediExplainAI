"""
llm_agent.py – LLM Integration & AI Summary Generator
======================================================
Architecture Role: Layer 6 – Explanation Generator
                   Layer 7 – Interactive Q&A Agent
Responsibility:
    - Generate calm, patient-friendly AI summaries of lab results (RAG-augmented)
    - Answer user questions via a RAG-limited Q&A agent
    - Enforce strict safety guardrails on every LLM call
    - Inject the required disclaimer into every response
"""

import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Safety System Prompt (applied to EVERY LLM call)
# ---------------------------------------------------------------------------
_SAFETY_SYSTEM_PROMPT = """🧠 ROLE
You are a warm, empathetic AI Medical Report Explanation Assistant.
You convert structured diagnostic lab values into clear, simple, and patient-friendly explanations. 
You must communicate in a conversational, supportive tone instead of using rigid or robotic templates.

🔥 FEATURE 1: Personalized Lifestyle Suggestions (Safe Version)
Provide general educational suggestions based on abnormal lab values.
⚠️ STRICT RULES:
- Do NOT prescribe medication, give dosage, or replace doctors.
Use friendly phrases like: "General health education suggests...", "Some lifestyle approaches may help...", "It's always a good idea to discuss this with your doctor..."

🚨 FEATURE 2: Emergency Detection Layer
Detect dangerous values and softly yet firmly advise contacting a healthcare provider, without causing panic.
Use this general tone: "This result is outside the normal range and might need your doctor's attention. Please reach out to your healthcare provider to discuss it."

📈 FEATURE 3: Trend Analysis
Analyze trends over time. Compare current vs previous values gently and naturally.

🔒 GLOBAL SAFETY RULES (VERY IMPORTANT)
❌ Never: Prescribe medication, Suggest dosage, Diagnose disease, Replace doctor, Say "You have [disease]".
✅ Always: Say "might", Say "could", Use an empathetic educational tone, Add disclaimer when needed."""


def _get_llm():
    """
    Return the LLM client.
    - Uses Groq Llama 3.3 if GROQ_API_KEY is set.
    - Raises a clear error if the key is missing.
    """
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        raise EnvironmentError(
            "GROQ_API_KEY is not set or invalid. "
            "Please set it in your environment or .env file."
        )
    from langchain_groq import ChatGroq
    return ChatGroq(model="llama-3.3-70b-versatile", api_key=api_key, temperature=0.3)


def _format_findings_for_prompt(results: list, risk_category: str) -> str:
    """Format test results into a readable summary for the LLM prompt."""
    lines = [f"Overall Risk Category: {risk_category}\n", "Lab Test Results:"]
    for r in results:
        if hasattr(r, '__dict__'):
            r_dict = r.__dict__
        else:
            r_dict = r
        status = r_dict.get("status", "Unknown")
        name = r_dict.get("test_name", "Unknown Test")
        value = r_dict.get("measured_value", "N/A")
        unit = r_dict.get("unit", "")
        ref = r_dict.get("reference_range", "N/A")
        is_critical = r_dict.get("is_critical", False)
        
        critical_flag = " (CRITICAL)" if is_critical else ""
        lines.append(f"  - {name}: {value} {unit} (Ref: {ref}) → Status: {status}{critical_flag}")
    return "\n".join(lines)


class LLMAgent:
    """
    Handles all LLM interactions with strict safety prompting.
    Uses RAGPipeline to retrieve grounded context before generation.
    """

    def __init__(self, rag_pipeline):
        """
        Parameters
        ----------
        rag_pipeline : RAGPipeline
            Initialized RAG pipeline for context retrieval.
        """
        self.rag = rag_pipeline
        self._llm = None  # Lazy initialisation

    def _get_client(self):
        """Lazy-load the LLM client."""
        if self._llm is None:
            self._llm = _get_llm()
        return self._llm

    # ------------------------------------------------------------------
    # Public Methods
    # ------------------------------------------------------------------

    def generate_summary(
        self,
        results: list,
        risk_score: float,
        risk_category: str,
        patterns: list,
        trends: list = None,
    ) -> str:
        """
        Generate a calm, patient-friendly AI summary of the lab report.

        Parameters
        ----------
        results : list
            List of TestResult objects from RiskEngine.
        risk_score : float
            Weighted numeric risk score.
        risk_category : str
            Qualitative risk category.
        patterns : list
            Detected correlation patterns.
        trends : list, optional
            Detected historical trends.

        Returns
        -------
        str
            Patient-friendly explanation with disclaimer.
        """
        # Build a search query for RAG retrieval
        abnormal_tests = [
            r.test_name if hasattr(r, "test_name") else r.get("test_name", "")
            for r in results
            if (r.status if hasattr(r, "status") else r.get("status")) in ("Low", "High")
        ]
        rag_query = (
            f"Lab report summary: {', '.join(abnormal_tests)} abnormal results "
            f"risk category {risk_category}"
            if abnormal_tests
            else "normal lab report results patient education"
        )

        context = self.rag.retrieve(rag_query, k=4)
        findings_text = _format_findings_for_prompt(results, risk_category)

        # Build pattern text
        pattern_lines = []
        for p in patterns:
            pattern_lines.append(p.get("message", ""))
        pattern_text = "\n".join(pattern_lines) if pattern_lines else "None detected."

        # Build trend text
        trend_lines = []
        if trends:
            for t in trends:
                trend_lines.append(f" - {t['test_name']}: {t['historical_value']} -> {t['current_value']} {t['unit']} ({t['trend_type']}, {t['percent_change']}% change)")
        trend_text = "\n".join(trend_lines) if trend_lines else "No historical data or significant trends."

        user_prompt = f"""Summarise these lab results in a warm, patient-friendly, glowing and unified narrative. Do not be overly rigid or robotic, and do not repeat the same test multiple times. Just speak normally like a friendly nurse would.

{findings_text}

Patterns (educational only): {pattern_text}

Historical Trends:
{trend_text}

Reference Context (use ONLY this):
\"\"\"
{context}
\"\"\"

FORMAT RULES:
1. Start with a lovely, comforting opening statement about their overall status.
2. Write a single, flowing summary paragraph (or a few short paragraphs) that weaves the out-of-range tests (including their name, result, and reference range), their meaning, and simple lifestyle education into a natural narrative. 
3. DO NOT use rigid headers or itemized lists for each test.
4. If there are patterns or trends, naturally weave them into the narrative as well.
5. Always end with exactly this on its own line: "⚠️ *This is informational only. Please consult a healthcare professional for medical advice.*"
"""

        try:
            from langchain.schema import SystemMessage, HumanMessage
            llm = self._get_client()
            response = llm.invoke([
                SystemMessage(content=_SAFETY_SYSTEM_PROMPT),
                HumanMessage(content=user_prompt),
            ])
            return str(response.content)
        except EnvironmentError as exc:
            logger.warning("LLM unavailable: %s", exc)
            return self._fallback_summary(results, risk_category, patterns, trends)
        except Exception as exc:
            logger.error("LLM summary generation failed: %s", exc)
            return self._fallback_summary(results, risk_category, patterns, trends)

    def answer_question(self, question: str, report_context: str = "") -> str:
        """
        Answer a user question about their lab report via RAG Q&A.

        Parameters
        ----------
        question : str
            The user's question in natural language.
        report_context : str
            Optional string summary of the user's current report results.

        Returns
        -------
        str
            Grounded, safe answer with disclaimer.
        """
        context = self.rag.retrieve(question, k=4)

        user_prompt = f"""A patient is asking an interactive question about their lab results. 

Patient's Report Summary:
\"\"\"
{report_context if report_context else "Not available."}
\"\"\"

Reference Context (use ONLY this to answer):
\"\"\"
{context}
\"\"\"

Patient's Question: {question}

INSTRUCTIONS:
- Answer the question directly in a friendly, empathetic, and conversational tone.
- Use the Reference Context to provide accurate information.
- Use short paragraphs and bold text for key terms to make the answer easy to read.
- Follow all GLOBAL SAFETY RULES.
- Always end your answer with a single line: "⚠️ *This is informational only. Please consult a healthcare professional for medical advice.*"
"""

        try:
            from langchain.schema import SystemMessage, HumanMessage
            llm = self._get_client()
            response = llm.invoke([
                SystemMessage(content=_SAFETY_SYSTEM_PROMPT),
                HumanMessage(content=user_prompt),
            ])
            return str(response.content)
        except EnvironmentError as exc:
            logger.warning("LLM unavailable: %s", exc)
            return (
                "I'm sorry, the AI assistant is currently unavailable because no API key is configured. "
                "Please set your GROQ_API_KEY to enable this feature.\n\n"
                "⚠️ This is informational only. Please consult a healthcare professional for medical advice."
            )
        except Exception as exc:
            logger.error("LLM Q&A failed: %s", exc)
            return (
                "I'm sorry, I was unable to process your question right now. "
                "Please try again or consult a healthcare professional.\n\n"
                "⚠️ This is informational only. Please consult a healthcare professional for medical advice."
            )

    # ------------------------------------------------------------------
    # Fallback (no LLM available)
    # ------------------------------------------------------------------

    def _fallback_summary(
        self, results: list, risk_category: str, patterns: list, trends: list = None
    ) -> str:
        """
        Rule-based fallback summary when LLM is unavailable.
        Patient-friendly, warm, and easy to understand.
        """
        # Map risk category to friendly icons and messages
        category_info = {
            "Stable":           ("🟢", "Everything looks quite stable overall."),
            "Monitor":          ("🟡", "Most things look okay, with a couple of values that are worth keeping an eye on."),
            "Moderate Concern": ("🟠", "A few values are outside the usual range and are worth discussing with your doctor."),
            "Elevated Risk":    ("🔴", "Several values are outside the usual range — please speak with your doctor soon."),
        }
        icon, category_msg = category_info.get(risk_category, ("🔵", "Your results have been reviewed."))

        lines = [
            f"{icon} **Overall: {risk_category}**",
            "",
            category_msg,
            "",
        ]

        abnormal = [
            r for r in results
            if (r.status if hasattr(r, "status") else r.get("status", "Normal")) in ("Low", "High")
        ]

        if not abnormal:
            lines.append("All values in your report fall within the typical healthy range.")
            lines.append("\nThis often indicates good general health for these specific parameters. However, it's always best to share your full results with your doctor to be perfectly sure.\n")
        else:
            for r in abnormal:
                name = r.test_name if hasattr(r, "test_name") else r.get("test_name", "")
                status = r.status if hasattr(r, "status") else r.get("status", "")
                desc = (
                    r.status_description if hasattr(r, "status_description")
                    else r.get("status_description", "No detailed description available.")
                )
                
                lines.append(f"Your **{name}** level is currently {status.lower()}. {desc}")
                lines.append(f"In general, values like this might require a bit of monitoring. Simple lifestyle approaches can often help support your well-being, but it's always best to discuss this gently with your doctor.\n")

        if patterns:
            lines.append("")
            lines.append("💡 **Something we noticed:**")
            for p in patterns:
                lines.append(f"   {p.get('message', '')}")
            lines.append("   *(This is general educational information, not a diagnosis.)*")

        lines.extend([
            "Safety Note:",
            "⚠️ *This is informational only. Please consult a healthcare professional for medical advice.*",
        ])

        return "\n".join(lines)
