"""
AI Invoice Extractor — LangChain + OpenRouter (Primary)
=========================================================
Architecture:
  1. OpenRouter (Primary) — free models, no quota burnout
     Model: google/gemini-2.0-flash-lite:free (configurable via OPENROUTER_MODEL)
     Token tracking via LangChain callbacks
     Temperature: AI_TEMPERATURE env var (default 0.0, fully deterministic)

  2. Google GenAI (Secondary) — gemini-1.5-flash-8b, 1M free req/day

  3. Regex Fallback (Always works) — extracts vendor, amount, invoice# from text

Usage:
    from app.services.ai_extractor import extract_invoice_data, InvoiceData
    result: InvoiceData = extract_invoice_data(email_body, sender=from_address)
"""

import re
import json
import logging
import io
from typing import Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("ai_extractor")


# ── Pydantic output schema ────────────────────────────────────────────────────

class InvoiceData(BaseModel):
    """Structured invoice data extracted from an email or PDF."""
    vendor_name:    Optional[str]   = Field(None, description="Vendor or supplier company name")
    invoice_number: Optional[str]   = Field(None, description="Invoice or bill reference number")
    amount:         Optional[float] = Field(None, description="Total invoice amount as a number")
    currency:       Optional[str]   = Field("USD", description="Currency code, e.g. USD, INR, EUR")
    invoice_date:   Optional[str]   = Field(None, description="Invoice date as YYYY-MM-DD if found")
    due_date:       Optional[str]   = Field(None, description="Payment due date as YYYY-MM-DD if found")
    is_invoice:     bool            = Field(False, description="True if this text is clearly an invoice or bill")
    confidence:     float           = Field(0.0, description="Confidence 0.0-1.0 that this is a real invoice")


# ── Prompt template ───────────────────────────────────────────────────────────

_SYSTEM = """You are a precise invoice data extraction assistant.
Given raw email or document text, extract invoice fields and return ONLY valid JSON.
Rules:
- Only set is_invoice=true when there is a clear bill, invoice, or payment request.
- Return null for any field you cannot find with high confidence.
- Do NOT guess or hallucinate values.
- amount must be a number (no currency symbols).

Return a JSON object with these keys:
  vendor_name    (string or null)
  invoice_number (string or null)
  amount         (number or null)
  currency       (string, e.g. USD)
  invoice_date   (YYYY-MM-DD string or null)
  due_date       (YYYY-MM-DD string or null)
  is_invoice     (true/false)
  confidence     (float 0.0-1.0)"""

_HUMAN = """--- EMAIL / DOCUMENT TEXT ---
{text}
--- END ---

Extract invoice data. Return only the JSON object, no explanation."""


# ── Token usage tracker ───────────────────────────────────────────────────────

class TokenTracker:
    """Accumulates token usage across all LangChain calls."""
    total_prompt_tokens:     int = 0
    total_completion_tokens: int = 0
    total_calls:             int = 0

    def record(self, usage: dict):
        self.total_prompt_tokens     += usage.get("prompt_tokens", 0)
        self.total_completion_tokens += usage.get("completion_tokens", 0)
        self.total_calls             += 1

    @property
    def total_tokens(self) -> int:
        return self.total_prompt_tokens + self.total_completion_tokens

    def summary(self) -> str:
        return (
            f"calls={self.total_calls}, "
            f"prompt={self.total_prompt_tokens}, "
            f"completion={self.total_completion_tokens}, "
            f"total={self.total_tokens}"
        )


# Singleton tracker (importable for dashboard/logging)
token_tracker = TokenTracker()


# ── LangChain + OpenRouter — multi-model resilient fallback ──────────────────

# Priority-ordered free models to try on OpenRouter.
# If one provider is rate-limited we automatically try the next.
_OPENROUTER_FREE_MODELS = [
    "qwen/qwen3-4b:free",
    "google/gemma-3-4b-it:free",
    "mistralai/mistral-small-3.1-24b-instruct:free",
    "nvidia/nemotron-nano-9b-v2:free",
]

_openrouter_api_key = None
_openrouter_temp    = 0.0
_genai_client       = None   # google.genai fallback


def _get_openrouter_key():
    """Return OpenRouter API key and temperature from settings (lazy load)."""
    global _openrouter_api_key, _openrouter_temp
    if _openrouter_api_key is not None:
        return _openrouter_api_key, _openrouter_temp
    try:
        import sys, os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        from config import settings
        if settings.OPENROUTER_API_KEY:
            _openrouter_api_key = settings.OPENROUTER_API_KEY
            _openrouter_temp    = settings.AI_TEMPERATURE
            logger.info(f"AI extractor: OpenRouter ready (temp={_openrouter_temp}, {len(_OPENROUTER_FREE_MODELS)} free models)")
    except Exception as e:
        logger.error(f"OpenRouter config load failed: {e}")
    return _openrouter_api_key, _openrouter_temp


def _call_openrouter(text: str) -> Optional[str]:
    """
    Try OpenRouter free models in priority order.
    Returns raw LLM text on success, None if all models fail.
    """
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import SystemMessage, HumanMessage

    api_key, temperature = _get_openrouter_key()
    if not api_key:
        return None

    human_text = _HUMAN.format(text=text)
    messages   = [SystemMessage(content=_SYSTEM), HumanMessage(content=human_text)]

    for model in _OPENROUTER_FREE_MODELS:
        try:
            llm = ChatOpenAI(
                model=model,
                openai_api_key=api_key,
                openai_api_base="https://openrouter.ai/api/v1",
                temperature=temperature,
                max_tokens=512,
                model_kwargs={
                    "extra_headers": {
                        "HTTP-Referer": "https://procure-iq.app",
                        "X-Title": "Procure-IQ Invoice Extractor",
                    }
                },
            )
            resp = llm.invoke(messages)
            raw  = resp.content
            # Track real token usage from response metadata
            usage = getattr(resp, "response_metadata", {}).get("token_usage", {})
            if usage:
                token_tracker.record(usage)
            else:
                token_tracker.record({
                    "prompt_tokens":     len(text) // 4,
                    "completion_tokens": len(raw) // 4,
                })
            logger.info(f"[OpenRouter/{model}] success | tracker: {token_tracker.summary()}")
            return raw
        except Exception as e:
            err = str(e)[:120]
            if "429" in err or "rate" in err.lower() or "quota" in err.lower():
                logger.warning(f"[OpenRouter/{model}] rate-limited, trying next model...")
            else:
                logger.warning(f"[OpenRouter/{model}] error: {err}, trying next model...")
    logger.error("All OpenRouter free models failed")
    return None


def _get_genai_client():
    """Lazy-init google.genai as secondary fallback (1M free req/day)."""
    global _genai_client
    if _genai_client is not None:
        return _genai_client
    try:
        import sys, os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        from config import settings
        import google.genai as genai

        if not settings.GEMINI_API_KEY:
            return None

        _genai_client = genai.Client(api_key=settings.GEMINI_API_KEY)
        logger.info("AI extractor: google.genai fallback ready")
        return _genai_client
    except Exception as e:
        logger.warning(f"google.genai init failed: {e}")
        return None


# ── Regex fallback extractor ─────────────────────────────────────────────────

def _regex_extract(text: str, sender: str = "") -> InvoiceData:
    """
    Robust regex extraction — runs when ALL AI options fail.
    No network calls. Always succeeds.
    """
    combined = text

    # ── Vendor name ──
    vendor_name = None
    for pat in [
        r'from\s+([A-Z][A-Za-z0-9\s&.,\-]{2,40})(?:\s*[\n,]|\s*$)',
        r'(?:vendor|supplier|company|billed\s+by)[:\s]+([A-Z][A-Za-z0-9\s&.,\-]{2,40})',
        r'(?:vendor|supplier)[:\s]+(.+)',
    ]:
        m = re.search(pat, combined, re.IGNORECASE | re.MULTILINE)
        if m:
            vendor_name = m.group(1).strip().rstrip(".,")[:60]
            break
    if not vendor_name and sender:
        m = re.match(r'^["\']?([^"\'<@\n]{2,50})["\']?\s*<', sender.strip())
        if m:
            vendor_name = m.group(1).strip().strip('"\'')
        else:
            m = re.search(r'@([a-zA-Z0-9\-]+)\.', sender)
            if m:
                vendor_name = m.group(1).title()

    # ── Invoice number ──
    invoice_number = None
    for pat in [
        r'(?:invoice|inv|bill|receipt|order)\s*(?:no\.?|num(?:ber)?|#)?\s*[:#]?\s*([A-Z0-9][-A-Z0-9]{2,20})',
        r'#\s*([A-Z0-9][-A-Z0-9]{2,20})',
    ]:
        m = re.search(pat, combined, re.IGNORECASE)
        if m:
            invoice_number = m.group(1).strip()
            break

    # ── Amount (most-specific to least-specific) ──
    amount = None
    for pat in [
        r'(?:total|grand\s+total|amount\s+due|balance\s+due)\s*[:\$]?\s*\$?\s*([\d,]+\.?\d*)',
        r'(?:amount|subtotal|total)\s*:\s*\$?\s*([\d,]+\.?\d*)',
        r'\$\s*([\d,]+\.\d{2})',
        r'([\d,]+\.\d{2})\s*(?:USD|INR|EUR|GBP)',
    ]:
        m = re.search(pat, combined, re.IGNORECASE)
        if m:
            try:
                amount = float(m.group(1).replace(",", ""))
                break
            except ValueError:
                continue

    # ── Invoice date ──
    invoice_date = None
    for pat in [
        r'(?:invoice\s+date|date|issued)[:\s]+(\d{4}-\d{2}-\d{2})',
        r'(?:invoice\s+date|date)[:\s]+(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})',
    ]:
        m = re.search(pat, combined, re.IGNORECASE)
        if m:
            invoice_date = m.group(1)
            break

    # ── Scoring ──
    kws = ['invoice', 'bill', 'receipt', 'amount due', 'payment due', 'purchase order']
    kw_hits = sum(1 for k in kws if k in combined.lower())
    is_invoice = kw_hits >= 1 or invoice_number is not None
    confidence = round(
        min(0.9, 0.4 + kw_hits * 0.12 + (0.1 if amount else 0) + (0.1 if invoice_number else 0)), 2
    )

    return InvoiceData(
        vendor_name=vendor_name,
        invoice_number=invoice_number,
        amount=amount,
        invoice_date=invoice_date,
        is_invoice=is_invoice,
        confidence=confidence,
    )


# ── JSON safe parser ──────────────────────────────────────────────────────────

def _parse_llm_json(raw: str) -> Optional[dict]:
    """Strip markdown fences and parse JSON, returning None on failure."""
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\s*|\s*```$", "", text, flags=re.DOTALL).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find a {...} block inside the text
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
    return None


# ── Main extraction function ──────────────────────────────────────────────────

def extract_invoice_data(text: str, max_chars: int = 3000, sender: str = "") -> InvoiceData:
    """
    Extract invoice data using a 3-tier strategy:

    Tier 1: LangChain + OpenRouter (free, no quota burnout, token tracking)
    Tier 2: google.genai gemini-1.5-flash-8b (1M free req/day)
    Tier 3: Regex regex from text (always succeeds, no network)

    Args:
        text:      Email body or PDF text
        max_chars: Truncate input to reduce token cost
        sender:    Sender address — used by fallback for vendor name
    Returns:
        InvoiceData model
    """
    truncated = text[:max_chars]

    # ── Tier 1: OpenRouter via LangChain (multi-model, free, token tracking) ───
    raw = _call_openrouter(truncated)
    if raw is not None:
        data = _parse_llm_json(raw)
        if data:
            result = InvoiceData(**{k: v for k, v in data.items() if k in InvoiceData.model_fields})
            logger.info(
                f"[OpenRouter] is_invoice={result.is_invoice}, "
                f"amount={result.amount}, vendor={result.vendor_name} | "
                f"tokens: {token_tracker.summary()}"
            )
            return result

    # ── Tier 2: google.genai direct ───────────────────────────────────────────
    client = _get_genai_client()
    if client is not None:
        try:
            prompt = f"{_SYSTEM}\n\n--- TEXT ---\n{truncated}\n--- END ---\n\nReturn only the JSON."
            response = client.models.generate_content(
                model="gemini-2.0-flash-lite",
                contents=prompt,
                config={"temperature": 0.0, "response_mime_type": "application/json"},
            )
            data = _parse_llm_json(response.text)
            if data:
                result = InvoiceData(**{k: v for k, v in data.items() if k in InvoiceData.model_fields})
                logger.info(
                    f"[Gemini-8b] is_invoice={result.is_invoice}, "
                    f"amount={result.amount}, vendor={result.vendor_name}"
                )
                return result
        except Exception as e:
            logger.warning(f"Gemini fallback failed: {e} — using regex extraction")

    # ── Tier 3: Regex (always works) ─────────────────────────────────────────
    result = _regex_extract(truncated, sender=sender)
    logger.info(
        f"[Regex] is_invoice={result.is_invoice}, "
        f"amount={result.amount}, vendor={result.vendor_name}, confidence={result.confidence}"
    )
    return result


# ── PDF text extractor ────────────────────────────────────────────────────────

def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract plain text from a PDF using pdfplumber (first 5 pages only)."""
    try:
        import pdfplumber
        parts = []
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages[:5]:
                t = page.extract_text()
                if t:
                    parts.append(t)
        return "\n".join(parts)
    except Exception as e:
        logger.warning(f"PDF extraction failed: {e}")
        return ""
