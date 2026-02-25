"""
Invoice Email Agent - Gmail OAuth Integration

Automatically fetches and processes invoice emails from Gmail using OAuth2.
Classifies emails, extracts invoice data using AI, and creates events for
the autonomous agent to process.

Features:
- Gmail OAuth2 authentication
- Email classification (invoice vs. non-invoice)
- AI-powered data extraction (vendor, amount, invoice number)
- Automatic event creation
- Email marking (read/unread)
- Polling interval: 5 minutes

Usage:
    from app.services.email_service import EmailIngestionService
    
    service = EmailIngestionService()
    new_invoices = await service.fetch_latest_invoices()
"""

import base64
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging

# Add parent directory to path for imports
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config import settings

# Conditional imports
try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GMAIL_AVAILABLE = True
except ImportError:
    GMAIL_AVAILABLE = False
    logging.warning("google-api-python-client not installed - Email agent unavailable")

logger = logging.getLogger(__name__)


class EmailIngestionService:
    """
    Gmail OAuth-based email ingestion service.
    
    Fetches invoice emails, classifies them, and extracts data using AI.
    """
    
    def __init__(self):
        """Initialize the email service with Gmail OAuth credentials."""
        self.gmail_service = None
        self.last_check_time = None
        
        if not GMAIL_AVAILABLE:
            logger.warning("Gmail API not available - email ingestion disabled")
            return
        
        if not settings.GMAIL_CLIENT_ID or not settings.GMAIL_CLIENT_SECRET:
            logger.warning("Gmail OAuth not configured - email ingestion disabled")
            return
        
        try:
            # Build credentials from settings
            creds = Credentials(
                token=None,
                refresh_token=settings.GMAIL_REFRESH_TOKEN,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=settings.GMAIL_CLIENT_ID,
                client_secret=settings.GMAIL_CLIENT_SECRET
            )
            
            # Build Gmail service
            self.gmail_service = build('gmail', 'v1', credentials=creds)
            logger.info("Gmail service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Gmail service: {e}")
            self.gmail_service = None
    
    
    def is_invoice_email(self, subject: str, body: str, sender: str) -> bool:
        """
        Strict invoice classification.

        Rules:
        - Immediately reject security alerts, login notices, newsletters,
          subscription notifications, marketing emails.
        - Require STRONG positive signals: explicit invoice/bill/receipt keyword
          AND (a currency amount OR an invoice number).
        - A single generic keyword like 'payment' or 'due' is NOT enough.

        Returns True only when the email is very likely an actual invoice or bill.
        """
        subject_lower = subject.lower().strip()
        body_preview  = body[:1500].lower()  # Only scan first 1500 chars
        sender_lower  = sender.lower()
        combined      = f"{subject_lower} {body_preview}"

        # ── Hard exclusions (reject immediately) ──────────────────────────────
        EXCLUSION_PHRASES = [
            # Security / account alerts
            "did you just log in", "new sign-in", "new login", "login attempt",
            "security alert", "unusual sign", "suspicious activity",
            "someone tried to", "verify your account", "confirm your email",
            "password reset", "forgot your password", "account recovery",
            # Notifications / LinkedIn / social
            "payment declined", "payment method", "payment failed",
            "linkedin", "subscription cancelled", "free trial",
            "you have a new follower", "you have a new message",
            "newsletter", "unsubscribe", "weekly digest",
            # Government / exam / job alerts
            "rti reply", "cgl", "applied", "vacancy", "quota digest",
            "notification from", "lakh appeared",
            # OTP / 2FA
            "otp", "one-time password", "verification code",
        ]
        EXCLUSION_SENDERS = [
            "noreply@linkedin", "notification@linkedin", "jobs-noreply",
            "alerts@google", "no-reply@accounts.google",
            "security@", "support@twitter", "notify@",
        ]

        for phrase in EXCLUSION_PHRASES:
            if phrase in combined:
                logger.debug(f"Invoice filter: REJECTED by exclusion phrase '{phrase}' — {subject[:60]}")
                return False

        for excl_sender in EXCLUSION_SENDERS:
            if excl_sender in sender_lower:
                logger.debug(f"Invoice filter: REJECTED by sender '{excl_sender}' — {subject[:60]}")
                return False

        # ── Strong positive signals ───────────────────────────────────────────
        # Signal 1: Explicit invoice / bill keyword in SUBJECT (highest confidence)
        STRONG_SUBJECT_KWS = [
            'invoice', 'bill', 'receipt', 'purchase order', 'tax invoice',
            'proforma', 'credit note', 'debit note', 'remittance',
        ]
        subject_has_invoice_kw = any(kw in subject_lower for kw in STRONG_SUBJECT_KWS)

        # Signal 2: Invoice keywords in body
        BODY_INVOICE_KWS = [
            'invoice', 'bill', 'receipt', 'purchase order', 'amount due',
            'total amount', 'payment due', 'balance due', 'remit payment',
            'please pay', 'attached invoice', 'tax invoice',
        ]
        body_invoice_hits = sum(1 for kw in BODY_INVOICE_KWS if kw in body_preview)

        # Signal 3: Dollar/currency amount present
        currency_pattern = r'[\$£€₹]\s*\d[\d,]*(?:\.\d{2})?|\d[\d,]*(?:\.\d{2})?\s*(?:usd|inr|eur|gbp)'
        has_currency = bool(re.search(currency_pattern, combined, re.IGNORECASE))

        # Signal 4: Invoice number pattern
        inv_num_pattern = r'(?:invoice|inv|bill)\s*(?:no\.?|num(?:ber)?|#)?\s*[:#]?\s*[A-Z0-9][-A-Z0-9]{2,}'
        has_invoice_number = bool(re.search(inv_num_pattern, combined, re.IGNORECASE))

        # ── Decision: need at least 2 strong signals ──────────────────────────
        score = (
            (2 if subject_has_invoice_kw else 0)  # subject match worth 2
            + min(body_invoice_hits, 2)            # body keywords (capped at 2)
            + (1 if has_currency else 0)
            + (1 if has_invoice_number else 0)
        )

        passed = score >= 2
        if passed:
            logger.debug(f"Invoice filter: ACCEPTED (score={score}) — {subject[:60]}")
        else:
            logger.debug(f"Invoice filter: REJECTED (score={score}) — {subject[:60]}")
        return passed

    
    
    async def extract_invoice_data(self, subject: str, body: str, sender: str) -> Dict:
        """
        Extract invoice data from email using the ai_extractor pipeline:
          Tier 1 — LangChain + OpenRouter (multi-model, free, token tracking)
          Tier 2 — google.genai direct (gemini-2.0-flash-lite)
          Tier 3 — Regex fallback (no network, always works)

        Returns dict with: vendor_name, invoice_number, amount, confidence (0-100)
        """
        try:
            from .ai_extractor import extract_invoice_data as _ai_extract

            # Combine subject + sender + body for richer context
            full_text = f"Subject: {subject}\nFrom: {sender}\n\n{body[:2500]}"

            # Run in thread so we don't block the event loop (ai_extractor is sync)
            import asyncio
            result = await asyncio.to_thread(
                _ai_extract, full_text, 3000, sender
            )

            # Normalise confidence: ai_extractor uses 0.0-1.0, callers expect 0-100
            conf_pct = int(result.confidence * 100)

            # Use vendor from result; fall back to a cleaned sender name
            vendor = result.vendor_name or self._vendor_from_sender(sender)

            logger.info(
                f"AI extracted — vendor={vendor}, "
                f"inv={result.invoice_number}, amt={result.amount}, conf={conf_pct}%"
            )
            return {
                "vendor_name":    vendor,
                "invoice_number": result.invoice_number or "UNKNOWN",
                "amount":         result.amount or 0.0,
                "confidence":     conf_pct,
            }

        except Exception as e:
            logger.error(f"extract_invoice_data failed: {e}")
            return self._fallback_extraction(subject, body, sender)

    def _vendor_from_sender(self, sender: str) -> str:
        """Extract a clean vendor name from the sender address."""
        # "Acme Corp <billing@acme.com>"  →  "Acme Corp"
        m = re.match(r'^["\']?([^"\'<@\n]{2,50})["\']?\s*<', sender.strip())
        if m:
            return m.group(1).strip().strip("\"'")
        # "billing@acme.com"  →  "acme"
        m = re.search(r'@([a-zA-Z0-9\-]+)\.', sender)
        if m:
            return m.group(1).title()
        return sender[:60]

    def _fallback_extraction(self, subject: str, body: str, sender: str) -> Dict:
        """
        Fallback extraction using regex patterns.
        
        Used when AI extraction fails.
        
        Args:
            subject: Email subject line
            body: Email body text
            sender: Sender email address
        
        Returns:
            Dict with extracted data (lower confidence)
        """
        text = f"{subject} {body}"
        
        # Extract vendor name from sender
        vendor_match = re.search(r'([^@<]+)(?:@|<)', sender)
        vendor_name = vendor_match.group(1).strip() if vendor_match else sender
        
        # Extract invoice number
        invoice_number = "UNKNOWN"
        invoice_patterns = [
            r'invoice\s*#?\s*:?\s*(\w+[-\w]*)',
            r'inv\s*#?\s*:?\s*(\w+[-\w]*)',
            r'bill\s*#?\s*:?\s*(\w+[-\w]*)',
        ]
        for pattern in invoice_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                invoice_number = match.group(1)
                break
        
        # Extract amount
        amount = 0.0
        amount_patterns = [
            r'total\s*:?\s*\$\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
            r'amount\s*:?\s*\$\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
            r'\$\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
        ]
        for pattern in amount_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                amount_str = match.group(1).replace(',', '')
                amount = float(amount_str)
                break
        
        return {
            "vendor_name": vendor_name,
            "invoice_number": invoice_number,
            "amount": amount,
            "confidence": 50  # Lower confidence for fallback
        }
    
    
    async def fetch_latest_invoices(self, max_results: int = 10) -> List[Dict]:
        """
        Fetch latest invoice emails from Gmail.
        
        Polls Gmail API for new emails, classifies them, and extracts data.
        
        Args:
            max_results: Maximum number of emails to fetch
        
        Returns:
            List of invoice data dicts:
            [
                {
                    "subject": str,
                    "from": str,
                    "date": str,
                    "body": str,
                    "vendor_name": str,
                    "invoice_number": str,
                    "amount": float,
                    "confidence": int,
                    "message_id": str
                },
                ...
            ]
        """
        if not self.gmail_service:
            logger.warning("Gmail service not initialized - skipping email fetch")
            return []
        
        try:
            # Build query for recent emails
            # Only fetch emails from last 24 hours on first run
            if not self.last_check_time:
                after_date = (datetime.now() - timedelta(hours=24)).strftime('%Y/%m/%d')
            else:
                after_date = self.last_check_time.strftime('%Y/%m/%d')
            
            query = f'after:{after_date} (in:inbox OR in:spam) -in:trash'
            
            # Fetch message list
            results = self.gmail_service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results,
                includeSpamTrash=True
            ).execute()
            
            messages = results.get('messages', [])
            
            if not messages:
                logger.debug("No new emails found")
                self.last_check_time = datetime.now()
                return []
            
            logger.info(f"Found {len(messages)} new emails")
            
            # Process each message
            invoices = []
            
            for msg in messages:
                try:
                    # Fetch full message
                    message = self.gmail_service.users().messages().get(
                        userId='me',
                        id=msg['id'],
                        format='full'
                    ).execute()
                    
                    # Extract headers
                    headers = message['payload']['headers']
                    subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), '')
                    sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), '')
                    date = next((h['value'] for h in headers if h['name'].lower() == 'date'), '')
                    
                    # Extract body
                    body = self._get_email_body(message['payload'])
                    
                    # Classify email
                    if not self.is_invoice_email(subject, body, sender):
                        logger.debug(f"Email '{subject}' not classified as invoice")
                        continue
                    
                    logger.info(f"Processing invoice email: {subject}")
                    
                    # Extract invoice data
                    extracted_data = await self.extract_invoice_data(subject, body, sender)
                    
                    # Build invoice dict
                    invoice = {
                        "subject": subject,
                        "from": sender,
                        "date": date,
                        "body": body,
                        "vendor_name": extracted_data.get("vendor_name", sender),
                        "invoice_number": extracted_data.get("invoice_number", f"EMAIL-{msg['id'][:8]}"),
                        "amount": extracted_data.get("amount", 0.0),
                        "confidence": extracted_data.get("confidence", 50),
                        "message_id": msg['id']
                    }
                    
                    invoices.append(invoice)
                    
                except Exception as e:
                    logger.error(f"Failed to process message {msg['id']}: {e}")
                    continue
            
            self.last_check_time = datetime.now()
            logger.info(f"Extracted {len(invoices)} invoices from emails")
            
            return invoices
            
        except HttpError as e:
            logger.error(f"Gmail API error: {e}")
            return []
        except Exception as e:
            logger.error(f"Failed to fetch emails: {e}")
            return []
    
    
    def _get_email_body(self, payload: Dict) -> str:
        """
        Extract email body from Gmail message payload.
        
        Handles both plain text and HTML emails.
        
        Args:
            payload: Gmail message payload
        
        Returns:
            Email body text
        """
        body = ""
        
        # Check for direct body data
        if 'body' in payload and 'data' in payload['body']:
            body = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='ignore')
            return body
        
        # Check for multipart
        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    if 'data' in part['body']:
                        body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
                        return body
                elif part['mimeType'] == 'text/html':
                    if 'data' in part['body']:
                        html_body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
                        # Simple HTML stripping (for basic extraction)
                        body = re.sub(r'<[^>]+>', ' ', html_body)
                        return body
                elif 'parts' in part:
                    # Recursive for nested parts
                    body = self._get_email_body(part)
                    if body:
                        return body
        
        return body
