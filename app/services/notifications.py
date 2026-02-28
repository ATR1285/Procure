"""
Real Notification Service — Gmail OAuth + Twilio SMS/WhatsApp

Sends real emails via Gmail API and real SMS/WhatsApp via Twilio.
Falls back to console logging if credentials are not configured.
"""

import logging
import os
import sys
import base64
from email.mime.text import MIMEText

# Config import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from config import settings

logger = logging.getLogger("Notifications")

# --- Conditional Imports ---
try:
    from twilio.rest import Client as TwilioClient
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False

try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    GMAIL_AVAILABLE = True
except ImportError:
    GMAIL_AVAILABLE = False


def _get_gmail_service():
    """Build Gmail API service using OAuth2 credentials from settings."""
    creds = Credentials(
        token=None,
        refresh_token=settings.GMAIL_REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GMAIL_CLIENT_ID,
        client_secret=settings.GMAIL_CLIENT_SECRET,
    )
    return build("gmail", "v1", credentials=creds)


def send_email_to_supplier(vendor_email: str, item_name: str, quantity: int) -> bool:
    """
    Send a restock order email to the supplier via Gmail OAuth.
    Falls back to console logging if Gmail is not configured.
    """
    subject = f"PURCHASE ORDER: Restock for {item_name}"
    body = (
        f"Hello,\n\n"
        f"Please supply {quantity} units of {item_name} at your earliest convenience.\n\n"
        f"This is an automated purchase order from Procure-IQ.\n\n"
        f"Regards,\nProcure-IQ Autonomous Agent"
    )

    # Try real Gmail first
    if GMAIL_AVAILABLE and getattr(settings, "GMAIL_REFRESH_TOKEN", None):
        try:
            service = _get_gmail_service()
            message = MIMEText(body)
            message["to"] = vendor_email
            message["subject"] = subject
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
            service.users().messages().send(userId="me", body={"raw": raw}).execute()
            logger.info(f"📧 [GMAIL SENT] To: {vendor_email} | Subject: {subject}")
            return True
        except Exception as e:
            logger.error(f"📧 Gmail send failed: {e}")

    # Fallback: log to console
    logger.info(f"📧 [EMAIL LOG] To: {vendor_email} | Subject: {subject}")
    print(f"\n--- EMAIL NOTIFICATION ---\nTo: {vendor_email}\nSubject: {subject}\nBody:\n{body}\n--------------------------\n")
    return False


def send_sms_to_owner(message: str) -> bool:
    """
    Send SMS to owner via Twilio. Falls back to console logging.
    """
    phone = getattr(settings, "OWNER_PHONE", None) or "+919894488506"

    if TWILIO_AVAILABLE and getattr(settings, "TWILIO_ACCOUNT_SID", None):
        try:
            client = TwilioClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            client.messages.create(
                body=message,
                from_=settings.TWILIO_FROM_NUMBER,
                to=phone,
            )
            logger.info(f"📱 [SMS SENT] To: {phone}")
            return True
        except Exception as e:
            logger.error(f"📱 SMS send failed: {e}")

    # Fallback: log to console
    logger.info(f"📱 [SMS LOG] To: {phone} | Message: {message}")
    print(f"\n--- SMS NOTIFICATION ---\nTo: {phone}\nMessage: {message}\n------------------------\n")
    return False


def send_whatsapp_to_owner(message: str) -> bool:
    """
    Send WhatsApp message to owner via Twilio. Falls back to console logging.
    """
    phone = getattr(settings, "OWNER_PHONE", None) or "+919894488506"

    if TWILIO_AVAILABLE and getattr(settings, "TWILIO_ACCOUNT_SID", None):
        try:
            client = TwilioClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            twilio_from = getattr(settings, "TWILIO_FROM_NUMBER", "")
            # Ensure whatsapp: prefix
            wa_from = twilio_from if twilio_from.startswith("whatsapp:") else f"whatsapp:{twilio_from}"
            wa_to = phone if phone.startswith("whatsapp:") else f"whatsapp:{phone}"
            client.messages.create(
                body=message,
                from_=wa_from,
                to=wa_to,
            )
            logger.info(f"💬 [WHATSAPP SENT] To: {phone}")
            return True
        except Exception as e:
            logger.warning(f"💬 WhatsApp send failed (non-critical): {e}")

    # Fallback: log to console
    logger.info(f"💬 [WHATSAPP LOG] To: {phone} | Message: {message}")
    return False
