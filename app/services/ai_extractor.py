"""
AI Invoice Extractor — LangChain + Gemini
==========================================
Uses LangChain's ChatGoogleGenerativeAI with:
  - temperature = 0.0   (deterministic, no hallucination)
  - max_tokens  = 512   (cheap, fast, sufficient for structured extraction)
  - with_structured_output() for reliable JSON

Extracts from email body text OR PDF attachment bytes.
"""

import logging
import io
from typing import Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("ai_extractor")

# ── Pydantic schema for structured output ─────────────────────────────────────

class InvoiceData(BaseModel):
    """Structured invoice data extracted from an email or PDF."""
    vendor_name:    Optional[str]   = Field(None, description="Vendor or supplier company name")
    invoice_number: Optional[str]   = Field(None, description="Invoice or bill reference number")
    amount:         Optional[float] = Field(None, description="Total invoice amount as a number")
    currency:       Optional[str]   = Field("USD", description="Currency code, e.g. USD, EUR")
    invoice_date:   Optional[str]   = Field(None, description="Invoice date as YYYY-MM-DD if found")
    due_date:       Optional[str]   = Field(None, description="Payment due date as YYYY-MM-DD if found")
    is_invoice:     bool            = Field(False, description="True if this text is clearly an invoice or bill")
    confidence:     float           = Field(0.0, description="Confidence 0.0-1.0 that this is a real invoice")


# ── LangChain client (lazy init) ──────────────────────────────────────────────

_llm = None

def _get_llm():
    """Lazily initialise the LangChain Gemini LLM (singleton)."""
    global _llm
    if _llm is not None:
        return _llm
    try:
        import sys, os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        from config import settings
        from langchain_google_genai import ChatGoogleGenerativeAI

        if not settings.GEMINI_API_KEY:
            logger.warning("GEMINI_API_KEY not set — AI extractor disabled")
            return None

        _llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",    # Fast & cheap
            google_api_key=settings.GEMINI_API_KEY,
            temperature=0.0,             # Fully deterministic
            max_output_tokens=512,       # Low tokens — we only need structured JSON
        )
        logger.info("AI extractor: Gemini 1.5 Flash ready (temp=0.0, max_tokens=512)")
        return _llm
    except Exception as e:
        logger.error(f"AI extractor init failed: {e}")
        return None


# ── Structured extractor ──────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are an invoice detection and data extraction assistant.
Given the following email or document text, extract invoice information.
Be conservative — only mark is_invoice=true if there is clear evidence of a bill or invoice.
Return null for fields you cannot find. Do not guess or hallucinate values."""


def extract_invoice_data(text: str, max_chars: int = 3000) -> InvoiceData:
    """
    Extract structured invoice data from raw text using LangChain + Gemini.
    
    Args:
        text: Email body or PDF text content
        max_chars: Truncate input to this length to control token usage
    
    Returns:
        InvoiceData pydantic model
    """
    llm = _get_llm()
    if llm is None:
        return InvoiceData()   # Fallback: empty result

    # Truncate to keep tokens low
    truncated = text[:max_chars]

    try:
        structured_llm = llm.with_structured_output(InvoiceData)
        result = structured_llm.invoke(
            f"{_SYSTEM_PROMPT}\n\n--- TEXT ---\n{truncated}\n--- END ---"
        )
        logger.debug(f"AI extractor: is_invoice={result.is_invoice}, amount={result.amount}, confidence={result.confidence}")
        return result
    except Exception as e:
        logger.warning(f"AI extraction failed: {e}")
        return InvoiceData()


# ── PDF text extractor ────────────────────────────────────────────────────────

def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """
    Extract plain text from a PDF attachment using pdfplumber.
    Returns empty string if extraction fails.
    """
    try:
        import pdfplumber
        text_parts = []
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages[:5]:   # Only first 5 pages to stay cheap
                t = page.extract_text()
                if t:
                    text_parts.append(t)
        return "\n".join(text_parts)
    except Exception as e:
        logger.warning(f"PDF extraction failed: {e}")
        return ""
