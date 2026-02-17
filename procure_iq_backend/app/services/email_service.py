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
        Classify email as invoice or non-invoice.
        
        Uses keyword matching and pattern detection to identify invoice emails.
        
        Args:
            subject: Email subject line
            body: Email body text
            sender: Sender email address
        
        Returns:
            True if email appears to be an invoice
        """
        # Invoice keywords
        invoice_keywords = [
            'invoice', 'bill', 'payment', 'receipt', 'statement',
            'purchase order', 'po#', 'order confirmation', 'quote',
            'estimate', 'due', 'amount due', 'total amount', 'balance'
        ]
        
        # Combine subject and body for analysis
        text = f"{subject} {body}".lower()
        
        # Check for invoice keywords
        keyword_matches = sum(1 for keyword in invoice_keywords if keyword in text)
        
        # Check for currency patterns
        currency_pattern = r'\$\s*\d+(?:,\d{3})*(?:\.\d{2})?'
        has_currency = bool(re.search(currency_pattern, text))
        
        # Check for invoice number patterns
        invoice_number_patterns = [
            r'invoice\s*#?\s*:?\s*(\w+[-\w]*)',
            r'inv\s*#?\s*:?\s*(\w+[-\w]*)',
            r'bill\s*#?\s*:?\s*(\w+[-\w]*)',
        ]
        has_invoice_number = any(re.search(pattern, text, re.IGNORECASE) for pattern in invoice_number_patterns)
        
        # Classification logic
        if keyword_matches >= 2 and has_currency:
            return True
        
        if has_invoice_number and has_currency:
            return True
        
        if keyword_matches >= 3:
            return True
        
        return False
    
    
    async def extract_invoice_data(self, subject: str, body: str, sender: str) -> Dict:
        """
        Extract invoice data from email using AI.
        
        Uses the AIClient to extract vendor name, amount, and invoice number.
        
        Args:
            subject: Email subject line
            body: Email body text
            sender: Sender email address
        
        Returns:
            Dict with extracted data:
            {
                "vendor_name": str,
                "invoice_number": str,
                "amount": float,
                "confidence": int (0-100)
            }
        """
        try:
            from ..agent.ai_client import get_ai_client
            
            # Build extraction prompt
            prompt = f"""
Extract invoice information from this email:

SUBJECT: {subject}
FROM: {sender}
BODY:
{body[:2000]}  # Limit to first 2000 chars

Extract the following information:
1. Vendor/Company Name
2. Invoice Number
3. Total Amount (in USD)

Return ONLY a JSON object in this format:
{{
  "vendor_name": "string",
  "invoice_number": "string",
  "amount": float,
  "confidence": 0-100
}}
"""
            
            system_instruction = """You are an invoice data extraction AI. 
            Extract vendor name, invoice number, and total amount from emails.
            Always return valid JSON with no markdown fences."""
            
            # Use AI client
            client = get_ai_client()
            response = await client.complete(
                prompt=prompt,
                system=system_instruction,
                json_mode=True,
                temperature=0.1,  # Low temperature for consistent extraction
                max_tokens=300
            )
            
            # Parse JSON response
            import json
            
            try:
                data = json.loads(response.content)
            except json.JSONDecodeError:
                # Try to extract JSON from markdown fences
                match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response.content, re.DOTALL)
                if match:
                    data = json.loads(match.group(1))
                else:
                    # Try to find any JSON object
                    match = re.search(r"(\{.*?\})", response.content, re.DOTALL)
                    if match:
                        data = json.loads(match.group(1))
                    else:
                        raise ValueError("Could not extract JSON from AI response")
            
            logger.info(f"Extracted invoice data: {data}")
            return data
            
        except Exception as e:
            logger.error(f"Failed to extract invoice data: {e}")
            
            # Fallback: basic regex extraction
            return self._fallback_extraction(subject, body, sender)
    
    
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
            
            query = f'after:{after_date} -in:spam -in:trash'
            
            # Fetch message list
            results = self.gmail_service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
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
