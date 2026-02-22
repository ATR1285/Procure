"""
OAuth Token Refresh Service
============================
Automatically refreshes the Gmail OAuth access token when a 401 is detected.
No manual re-run of gmail_auth_setup.py needed.
"""

import logging
from typing import Optional

logger = logging.getLogger("token_refresh")


def get_fresh_credentials():
    """
    Build and auto-refresh Gmail OAuth credentials.
    Returns a valid Credentials object, or None if not configured.
    """
    try:
        import sys, os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        from config import settings
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request

        if not settings.GMAIL_CLIENT_ID or not settings.GMAIL_REFRESH_TOKEN:
            logger.warning("Gmail OAuth not configured — skipping token refresh")
            return None

        creds = Credentials(
            token=None,
            refresh_token=settings.GMAIL_REFRESH_TOKEN,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.GMAIL_CLIENT_ID,
            client_secret=settings.GMAIL_CLIENT_SECRET,
        )

        # Force a refresh to get a valid access token
        creds.refresh(Request())
        logger.info("Gmail token refreshed successfully ✓")
        return creds

    except Exception as e:
        logger.error(f"Token refresh failed: {e}")
        return None


def build_gmail_service_with_refresh() -> Optional[object]:
    """
    Build an authenticated Gmail API service, auto-refreshing the token.
    Returns None if credentials are missing or refresh fails.
    """
    try:
        from googleapiclient.discovery import build
        creds = get_fresh_credentials()
        if creds is None:
            return None
        service = build("gmail", "v1", credentials=creds)
        logger.info("Gmail service built with fresh token ✓")
        return service
    except Exception as e:
        logger.error(f"Gmail service build failed: {e}")
        return None
