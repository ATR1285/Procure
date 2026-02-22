"""
API routes for credential management.
Keys are NEVER returned in plaintext unless the user has just re-authenticated.
"""
import datetime
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..database import get_db
from ..credentials import (
    get_all_credentials_masked,
    get_plaintext_for_verified_user,
    set_credential,
    CREDENTIAL_CATALOGUE
)

router = APIRouter(prefix="/api/credentials", tags=["credentials"])


def _is_secrets_verified(request: Request) -> bool:
    """
    Check that the user completed re-auth within the last 5 minutes.
    """
    if not request.session.get("secrets_verified"):
        return False
    verified_at_str = request.session.get("secrets_verified_at")
    if not verified_at_str:
        return False
    try:
        verified_at = datetime.datetime.fromisoformat(verified_at_str)
        elapsed = (datetime.datetime.utcnow() - verified_at).total_seconds()
        return elapsed < 300  # 5 minutes
    except Exception:
        return False


# ─── List all credentials (masked) ───────────────────────

@router.get("/")
async def list_credentials(request: Request):
    """Returns all credentials with masked values. No secrets visible."""
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {"credentials": get_all_credentials_masked()}


# ─── Reveal a single plaintext value (re-auth required) ──

@router.get("/reveal/{key}")
async def reveal_credential(key: str, request: Request):
    """
    Returns the PLAINTEXT value of a credential.
    Requires Google re-authentication (verified in last 5 minutes).
    """
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not _is_secrets_verified(request):
        return JSONResponse(
            status_code=403,
            content={
                "error": "reauth_required",
                "message": "Google re-authentication required to view secrets.",
                "reauth_url": "/auth/reauth"
            }
        )

    if key not in CREDENTIAL_CATALOGUE:
        raise HTTPException(status_code=404, detail="Unknown credential key")

    value = get_plaintext_for_verified_user(key)
    return {"key": key, "value": value or ""}


# ─── Save / update a credential ──────────────────────────

class CredentialUpdate(BaseModel):
    key: str
    value: str

@router.post("/save")
async def save_credential(body: CredentialUpdate, request: Request, db: Session = Depends(get_db)):
    """
    Save a credential to the database.
    The value is stored but NEVER echoed back.
    """
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if body.key not in CREDENTIAL_CATALOGUE:
        raise HTTPException(status_code=400, detail=f"Unknown key '{body.key}'")

    if not body.value or not body.value.strip():
        raise HTTPException(status_code=400, detail="Value cannot be empty")

    ok = set_credential(body.key, body.value, db=db)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to save credential")

    return {"success": True, "key": body.key, "message": f"'{body.key}' saved successfully."}


# ─── Check re-auth status ─────────────────────────────────

@router.get("/reauth-status")
async def reauth_status(request: Request):
    """Client can poll this to know if the user has verified recently."""
    verified = _is_secrets_verified(request)
    return {"verified": verified}
