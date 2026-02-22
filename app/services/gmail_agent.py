"""
Gmail Invoice Agent — Background poller (v2)
=============================================
Scans owner's Gmail INBOX and SPAM every GMAIL_POLL_INTERVAL seconds.
New in v2:
  - Uses LangChain + Gemini AI for intelligent invoice detection & extraction
  - Parses PDF attachments via pdfplumber
  - Auto-refreshes OAuth token (no manual re-auth needed)
  - Deduplicates by (message_id) AND (subject + sender) to catch forwarded mails
  - Poll interval from GMAIL_POLL_INTERVAL env var (default 60s)
"""

import asyncio
import base64
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger("gmail_agent")

# ── Agent state (shared, readable by /api/agent-status) ──────────────────────
agent_state = {
    "status": "starting",
    "last_scan": None,
    "scans_today": 0,
    "invoices_today": 0,
    "last_error": None,
}


# ── Gmail helpers ─────────────────────────────────────────────────────────────

def _decode_body(payload) -> str:
    """Recursively extract plain-text body from a Gmail message payload."""
    body = ""
    if "parts" in payload:
        for part in payload["parts"]:
            body += _decode_body(part)
    else:
        data = payload.get("body", {}).get("data", "")
        if data:
            try:
                body = base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="ignore")
            except Exception:
                pass
    return body


def _get_header(headers, name: str) -> str:
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def _extract_pdf_attachments(service, msg_id: str, payload) -> list[bytes]:
    """Download all PDF attachment bytes from a message."""
    pdfs = []
    parts = payload.get("parts", [])
    for part in parts:
        filename = part.get("filename", "")
        mimetype = part.get("mimeType", "")
        if "pdf" in mimetype.lower() or filename.lower().endswith(".pdf"):
            att_id = part.get("body", {}).get("attachmentId")
            if att_id:
                try:
                    att = service.users().messages().attachments().get(
                        userId="me", messageId=msg_id, id=att_id
                    ).execute()
                    data = att.get("data", "")
                    if data:
                        pdfs.append(base64.urlsafe_b64decode(data + "=="))
                except Exception as e:
                    logger.warning(f"PDF download failed for {msg_id}: {e}")
    return pdfs


# ── DB helpers ────────────────────────────────────────────────────────────────

def _is_duplicate(db, msg_id: str, subject: str, sender: str) -> bool:
    """Dedup by Gmail message_id OR by (subject + sender) for forwarded emails."""
    from ..models import GmailInvoice
    by_id = db.query(GmailInvoice).filter(GmailInvoice.message_id == msg_id).first()
    if by_id:
        return True
    by_content = (
        db.query(GmailInvoice)
        .filter(GmailInvoice.subject == subject[:255], GmailInvoice.sender == sender[:255])
        .first()
    )
    return by_content is not None


def _save_to_db(db, msg_id, subject, sender, amount, inv_number,
                inv_date, vendor_name, confidence, received_at, found_in_spam) -> bool:
    from ..models import GmailInvoice
    if _is_duplicate(db, msg_id, subject or "", sender or ""):
        return False
    row = GmailInvoice(
        message_id=msg_id,
        subject=(subject or "")[:255],
        sender=(sender or "")[:255],
        amount=amount or 0.0,
        invoice_number=inv_number,
        invoice_date=inv_date,
        vendor_name=(vendor_name or "")[:255],
        confidence=confidence,
        received_at=received_at,
        found_in_spam=found_in_spam,
        status="PENDING_REVIEW",
        audit_trail=[{"t": datetime.utcnow().isoformat(), "a": "detected",
                      "m": f"Found by Gmail agent in {'SPAM' if found_in_spam else 'INBOX'}"}],
    )
    db.add(row)
    db.commit()
    logger.info(f"Gmail agent: saved — {(subject or '')[:60]} | ${amount} | conf={confidence:.0%}")
    return True


# ── Core scan ─────────────────────────────────────────────────────────────────

def _scan_label(service, db, label: str, after_date: str,
                found_in_spam: bool, max_results: int = 20) -> int:
    """Scan one Gmail label, classify with AI, extract from PDFs, save invoices."""
    from ..services.ai_extractor import extract_invoice_data, extract_text_from_pdf

    try:
        result = service.users().messages().list(
            userId="me", labelIds=[label], q=f"after:{after_date}", maxResults=max_results
        ).execute()
        messages = result.get("messages", [])
    except Exception as e:
        logger.error(f"Gmail agent: list {label} failed — {e}")
        return 0

    saved = 0
    for ref in messages:
        try:
            msg = service.users().messages().get(
                userId="me", id=ref["id"], format="full"
            ).execute()
            payload  = msg.get("payload", {})
            headers  = payload.get("headers", [])
            subject  = _get_header(headers, "Subject")
            sender   = _get_header(headers, "From")
            date_str = _get_header(headers, "Date")
            body     = _decode_body(payload)

            # Try PDF attachments first (higher quality)
            pdf_bytes_list = _extract_pdf_attachments(service, ref["id"], payload)
            pdf_text = ""
            for pdf_bytes in pdf_bytes_list:
                pdf_text += extract_text_from_pdf(pdf_bytes) + "\n"

            # Combine: subject + body + PDF text
            full_text = f"Subject: {subject}\nFrom: {sender}\n\n{body}\n\n{pdf_text}"

            # AI extraction (LangChain + Gemini)
            inv_data = extract_invoice_data(full_text)

            if not inv_data.is_invoice or inv_data.confidence < 0.4:
                continue  # Not an invoice — skip

            try:
                received_at = datetime.strptime(date_str[:25].strip(), "%a, %d %b %Y %H:%M:%S")
            except Exception:
                received_at = datetime.utcnow()

            if _save_to_db(
                db, ref["id"], subject, sender,
                inv_data.amount, inv_data.invoice_number,
                inv_data.invoice_date, inv_data.vendor_name,
                inv_data.confidence, received_at, found_in_spam
            ):
                saved += 1

        except Exception as e:
            logger.warning(f"Gmail agent: error on msg {ref.get('id')} — {e}")

    return saved


# ── Background loop ───────────────────────────────────────────────────────────

async def gmail_invoice_agent(get_db_func, poll_interval: int = 60):
    """
    Infinite async loop — launched as a FastAPI background task on startup.
    poll_interval is overridden by GMAIL_POLL_INTERVAL env var if set.
    """
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

    # Respect env override for poll interval
    try:
        poll_interval = int(os.environ.get("GMAIL_POLL_INTERVAL", poll_interval))
    except ValueError:
        pass

    logger.info("Gmail Invoice Agent v2 started — poll every %ds", poll_interval)
    agent_state["status"] = "running"

    from .token_refresh import build_gmail_service_with_refresh
    service = None

    while True:
        try:
            # Auto-refresh connection each cycle
            service = build_gmail_service_with_refresh()

            if service:
                db = next(get_db_func())
                try:
                    after = (datetime.utcnow() - timedelta(days=1)).strftime("%Y/%m/%d")
                    inbox = _scan_label(service, db, "INBOX", after, False)
                    spam  = _scan_label(service, db, "SPAM",  after, True)
                    total = inbox + spam

                    agent_state["last_scan"]      = datetime.utcnow().isoformat()
                    agent_state["scans_today"]    += 1
                    agent_state["invoices_today"] += total
                    agent_state["last_error"]      = None
                    if total:
                        logger.info("Agent: +%d inbox / +%d spam invoices found", inbox, spam)
                finally:
                    db.close()
            else:
                agent_state["status"] = "waiting_credentials"
                await asyncio.sleep(300)
                continue

        except Exception as e:
            agent_state["last_error"] = str(e)
            agent_state["status"] = "error"
            logger.error(f"Gmail agent cycle error: {e}")
            service = None

        agent_state["status"] = "running"
        await asyncio.sleep(poll_interval)
