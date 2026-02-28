import os
import datetime
import hashlib

from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .database import get_db
from . import models

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

router = APIRouter(tags=["auth"])


# ─── Helpers ──────────────────────────────────────────────

def _hash_password(password: str) -> str:
    salt = os.urandom(16).hex()
    hashed = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}:{hashed}"


def _verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, hashed = stored_hash.split(":", 1)
        return hashlib.sha256((salt + password).encode()).hexdigest() == hashed
    except Exception:
        return False


# ─── Login ────────────────────────────────────────────────

@router.post("/auth/password-login")
async def password_login(request: Request, db: Session = Depends(get_db)):
    """Login with email and password."""
    form = await request.form()
    email    = str(form.get("email", "")).strip().lower()
    password = str(form.get("password", ""))

    if not email or not password:
        return RedirectResponse("/login?error=missing_fields", status_code=303)

    user = db.query(models.User).filter(models.User.email == email).first()

    if not user or not user.password_hash:
        return RedirectResponse("/login?error=invalid_credentials", status_code=303)

    if not _verify_password(password, user.password_hash):
        return RedirectResponse("/login?error=invalid_credentials", status_code=303)

    if not user.is_active:
        return RedirectResponse("/login?error=account_disabled", status_code=303)

    user.last_login = datetime.datetime.utcnow()
    db.commit()

    request.session["user"] = {
        "email":    user.email,
        "name":     user.name,
        "picture":  user.picture,
        "is_admin": user.is_admin,
    }
    return RedirectResponse("/", status_code=303)


# ─── First-time Setup ─────────────────────────────────────

@router.get("/auth/setup")
async def setup_page(request: Request, db: Session = Depends(get_db)):
    """Show setup form if no admin exists yet."""
    has_users = db.query(models.User).count() > 0
    error = request.query_params.get("error", "")
    return templates.TemplateResponse("login.html", {
        "request":      request,
        "setup_mode":   not has_users,
        "setup_locked": has_users,
        "error":        error,
    })


@router.post("/auth/setup")
async def create_admin(request: Request, db: Session = Depends(get_db)):
    """Create the first admin (locked once a user exists)."""
    if db.query(models.User).count() > 0:
        return RedirectResponse("/login?error=setup_locked", status_code=303)

    form     = await request.form()
    email    = str(form.get("email", "")).strip().lower()
    name     = str(form.get("name", "Admin")).strip()
    password = str(form.get("password", ""))

    if not email or not password or len(password) < 6:
        return RedirectResponse("/auth/setup?error=invalid_input", status_code=303)

    user = models.User(
        email=email,
        name=name,
        password_hash=_hash_password(password),
        is_active=True,
        is_admin=True,
    )
    db.add(user)
    db.commit()

    request.session["user"] = {
        "email":    user.email,
        "name":     user.name,
        "picture":  None,
        "is_admin": True,
    }
    return RedirectResponse("/", status_code=303)


# ─── Logout ───────────────────────────────────────────────

@router.get("/auth/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login")
