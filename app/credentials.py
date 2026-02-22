"""
Procure-IQ Credential Service
==============================
Single source of truth for all API keys and secrets.

Priority:
  1. Database (app_settings table) — set via Settings UI
  2. Environment variables (.env file) — fallback

Security rules:
  - get_credential()         → always works (for internal use only)
  - get_masked_credential()  → returns "****...XXXX" for display
  - get_plaintext_credential() → ONLY after Google re-auth (session flag)
"""

import datetime
import logging
from typing import Optional
from sqlalchemy.orm import Session

logger = logging.getLogger("Credentials")

# Lazy import to avoid circular deps
def _get_db():
    from .database import SessionLocal
    return SessionLocal()

def _get_settings():
    from config import settings
    return settings


# ──────────────────────────────────────────────────────────
# Known credentials catalogue (key → description)
# ──────────────────────────────────────────────────────────
CREDENTIAL_CATALOGUE = {
    "GOOGLE_CLIENT_ID":     ("Google OAuth Client ID",     True),
    "GOOGLE_CLIENT_SECRET": ("Google OAuth Client Secret", True),
    "GEMINI_API_KEY":       ("Google Gemini API Key",      True),
    "OPENAI_API_KEY":       ("OpenAI API Key",             True),
    "GMAIL_CLIENT_ID":      ("Gmail OAuth Client ID",      True),
    "GMAIL_CLIENT_SECRET":  ("Gmail OAuth Client Secret",  True),
    "GMAIL_REFRESH_TOKEN":  ("Gmail Refresh Token",        True),
    "API_KEY":              ("App Master API Key",         True),
    "OPENROUTER_API_KEY":   ("OpenRouter API Key",         True),
}


# ──────────────────────────────────────────────────────────
# Core read / write
# ──────────────────────────────────────────────────────────

def get_credential(key: str, default: Optional[str] = None) -> Optional[str]:
    """
    Internal-use only. Returns the raw value of a credential.
    Priority: DB → .env → default
    """
    # 1. Try database
    try:
        from . import models
        db = _get_db()
        try:
            row = db.query(models.AppSetting).filter(models.AppSetting.key == key).first()
            if row and row.value and row.value.strip():
                return row.value.strip()
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"[CREDS] DB lookup failed for '{key}': {e}")

    # 2. Fall back to .env / settings
    try:
        settings = _get_settings()
        env_val = getattr(settings, key, None)
        if env_val and str(env_val).strip():
            return str(env_val).strip()
    except Exception:
        pass

    return default


def set_credential(key: str, value: str, db: Session = None) -> bool:
    """
    Save or update a credential in the database.
    """
    close_db = False
    try:
        if db is None:
            from . import models
            db = _get_db()
            close_db = True

        from . import models
        desc, is_secret = CREDENTIAL_CATALOGUE.get(key, (key, True))
        row = db.query(models.AppSetting).filter(models.AppSetting.key == key).first()
        if row:
            row.value = value.strip()
            row.updated_at = datetime.datetime.utcnow()
        else:
            row = models.AppSetting(
                key=key,
                value=value.strip(),
                description=desc,
                is_secret=is_secret,
            )
            db.add(row)
        db.commit()
        logger.info(f"[CREDS] Updated '{key}' in DB.")
        return True
    except Exception as e:
        logger.error(f"[CREDS] Failed to save '{key}': {e}")
        return False
    finally:
        if close_db and db:
            db.close()


# ──────────────────────────────────────────────────────────
# Display helpers
# ──────────────────────────────────────────────────────────

def mask_value(value: Optional[str]) -> str:
    """Return a masked display string: '••••••••XXXX' (last 4 chars visible)."""
    if not value:
        return "Not configured"
    if len(value) <= 4:
        return "••••"
    return f"••••••••{value[-4:]}"


def get_masked_credential(key: str) -> str:
    """Returns masked value for safe display in UI."""
    return mask_value(get_credential(key))


def get_all_credentials_masked() -> list[dict]:
    """
    Returns all known credentials with masked values and metadata.
    Safe to return in API responses — no plaintext secrets.
    """
    result = []
    for key, (description, is_secret) in CREDENTIAL_CATALOGUE.items():
        raw = get_credential(key)
        # Check if it came from DB
        from_db = False
        try:
            from . import models
            db = _get_db()
            try:
                row = db.query(models.AppSetting).filter(models.AppSetting.key == key).first()
                from_db = bool(row and row.value)
            finally:
                db.close()
        except Exception:
            pass

        result.append({
            "key": key,
            "description": description,
            "is_secret": is_secret,
            "is_set": bool(raw),
            "from_db": from_db,
            "masked_value": mask_value(raw) if is_secret else (raw or "Not configured"),
        })
    return result


def get_plaintext_for_verified_user(key: str) -> Optional[str]:
    """
    Returns FULL plaintext value.
    ONLY call this from endpoints that have verified Google re-auth in the current session.
    """
    return get_credential(key)
