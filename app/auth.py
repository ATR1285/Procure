import os
import datetime

# Allow HTTP for local development (remove in production)
os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
import google_auth_oauthlib.flow
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from .database import get_db
from . import models
from config import settings


router = APIRouter(tags=["auth"])

# OAuth config loaded via credential service (DB-first, .env fallback)
REDIRECT_URI_PATH = "/auth/callback"
REAUTH_REDIRECT_URI_PATH = "/auth/reauth/callback"

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile"
]

def _get_oauth_config():
    from .credentials import get_credential
    client_id = get_credential("GOOGLE_CLIENT_ID") or settings.GOOGLE_CLIENT_ID
    client_secret = get_credential("GOOGLE_CLIENT_SECRET") or settings.GOOGLE_CLIENT_SECRET
    return client_id, client_secret

def _build_flow(client_id, client_secret, redirect_uri, state=None):
    kwargs = {}
    if state:
        kwargs["state"] = state
    return google_auth_oauthlib.flow.Flow.from_client_config(
        {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=SCOPES,
        **kwargs
    )

# ─── Primary Login ────────────────────────────────────────

@router.get("/auth/login")
async def login(request: Request):
    client_id, client_secret = _get_oauth_config()
    if not client_id or not client_secret:
        return RedirectResponse("/login?error=google_not_configured")

    base_url = str(request.base_url).rstrip("/")
    redirect_uri = f"{base_url}{REDIRECT_URI_PATH}"

    flow = _build_flow(client_id, client_secret, redirect_uri)
    flow.redirect_uri = redirect_uri
    authorization_url, state = flow.authorization_url(access_type="offline", include_granted_scopes="false")

    request.session["oauth_state"] = state
    request.session["oauth_redirect"] = redirect_uri
    return RedirectResponse(authorization_url)


@router.get("/auth/callback")
async def callback(request: Request, db: Session = Depends(get_db)):
    state = request.session.get("oauth_state")
    redirect_uri = request.session.get("oauth_redirect")
    if not state:
        return RedirectResponse("/login?error=invalid_state")

    client_id, client_secret = _get_oauth_config()
    try:
        flow = _build_flow(client_id, client_secret, redirect_uri, state=state)
        flow.redirect_uri = redirect_uri
        flow.fetch_token(authorization_response=str(request.url))
        credentials = flow.credentials

        id_info = id_token.verify_oauth2_token(
            credentials.id_token, google_requests.Request(), client_id
        )
        email = id_info.get("email")
        name = id_info.get("name")
        picture = id_info.get("picture")

        # Check/Create user
        user = db.query(models.User).filter(models.User.email == email).first()
        if not user:
            is_admin = db.query(models.User).count() == 0
            user = models.User(email=email, name=name, picture=picture, is_active=True, is_admin=is_admin)
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            user.last_login = datetime.datetime.utcnow()
            user.picture = picture
            db.commit()

        if not user.is_active:
            return RedirectResponse("/login?error=account_disabled")

        request.session["user"] = {
            "email": user.email,
            "name": user.name,
            "picture": user.picture,
            "is_admin": user.is_admin
        }
        request.session.pop("oauth_state", None)
        request.session.pop("oauth_redirect", None)

        return RedirectResponse("/")

    except Exception as e:
        print(f"[AUTH] Login error: {e}")
        return RedirectResponse("/login?error=auth_failed")


# ─── Re-Authentication (to view secrets) ─────────────────

@router.get("/auth/reauth")
async def reauth(request: Request):
    """
    Requires a fresh Google login before allowing plaintext credential access.
    Sets a short-lived 'verified' flag in session on success.
    """
    client_id, client_secret = _get_oauth_config()
    if not client_id or not client_secret:
        return JSONResponse({"error": "Google auth not configured"}, status_code=400)

    base_url = str(request.base_url).rstrip("/")
    redirect_uri = f"{base_url}{REAUTH_REDIRECT_URI_PATH}"

    flow = _build_flow(client_id, client_secret, redirect_uri)
    flow.redirect_uri = redirect_uri
    authorization_url, state = flow.authorization_url(access_type="offline")

    request.session["reauth_state"] = state
    request.session["reauth_redirect"] = redirect_uri
    return RedirectResponse(authorization_url)


@router.get("/auth/reauth/callback")
async def reauth_callback(request: Request):
    state = request.session.get("reauth_state")
    redirect_uri = request.session.get("reauth_redirect")
    if not state:
        return RedirectResponse("/settings?error=invalid_reauth_state")

    client_id, client_secret = _get_oauth_config()
    try:
        flow = _build_flow(client_id, client_secret, redirect_uri, state=state)
        flow.redirect_uri = redirect_uri
        flow.fetch_token(authorization_response=str(request.url))
        credentials = flow.credentials

        id_info = id_token.verify_oauth2_token(
            credentials.id_token, google_requests.Request(), client_id
        )
        # Verify the re-authing user matches the logged-in user
        session_user = request.session.get("user")
        if session_user and id_info.get("email") != session_user.get("email"):
            return RedirectResponse("/settings?error=reauth_user_mismatch")

        # Set verified flag (expires in 5 minutes)
        request.session["secrets_verified"] = True
        request.session["secrets_verified_at"] = datetime.datetime.utcnow().isoformat()
        request.session.pop("reauth_state", None)
        request.session.pop("reauth_redirect", None)

        return RedirectResponse("/settings?tab=credentials&verified=1")

    except Exception as e:
        print(f"[AUTH] Reauth error: {e}")
        return RedirectResponse("/settings?error=reauth_failed")


# ─── Logout ───────────────────────────────────────────────

@router.get("/auth/logout")
async def logout(request: Request):
    error = request.query_params.get("error", "")
    request.session.clear()
    url = f"/login?error={error}" if error else "/login"
    return RedirectResponse(url)
