"""
Procure-IQ Main Application
"""

import os
import sys

# ⚠️ DEV ONLY: allow OAuth over http://localhost
if os.environ.get("RENDER") or os.environ.get("RAILWAY_ENVIRONMENT"):
    pass  # Production: HTTPS is automatic
else:
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

# Allow Google to return extra previously-granted scopes (e.g. gmail.modify)
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

import time
import secrets
import threading
import datetime
import logging

# ── Production Logging ────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ProcureIQ")


from fastapi import FastAPI, Depends, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

# Add parent directory to path for config import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings
from . import models, schemas, auth
from .database import SessionLocal, engine
from .models import Base
from .agent.worker import start_agent_loop
from .services.gmail_agent import gmail_invoice_agent, agent_state
from .database import get_db
import asyncio
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)

# --- Monitoring & Error Tracking ---
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from .middleware.monitoring import PrometheusMiddleware, get_metrics

if settings.API_KEY:
    sentry_sdk.init(
        dsn=getattr(settings, "SENTRY_DSN", ""),
        integrations=[FastApiIntegration()],
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
    )

# ── Lifespan: start background agents on startup ─────────────────────────────
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    # Print configuration summary
    settings.print_startup_summary()
    
    # 1. Start Gmail Invoice Agent (Async) — non-fatal
    try:
        asyncio.create_task(
            gmail_invoice_agent(get_db, poll_interval=settings.GMAIL_POLL_INTERVAL)
        )
        print("[STARTUP] Gmail agent started")
    except Exception as e:
        print(f"[STARTUP] Gmail agent failed (non-fatal): {e}")
    
    # 2. Start Inventory Agent (Threaded) — non-fatal
    try:
        threading.Thread(target=start_agent_loop, daemon=True).start()
        print("[STARTUP] Inventory agent started")
    except Exception as e:
        print(f"[STARTUP] Inventory agent failed (non-fatal): {e}")
    
    yield

# --- App Initialization ---
app = FastAPI(
    title="Procure-IQ API",
    version="2.0.0",
    description="Intelligent Autonomous Procurement System",
    lifespan=lifespan
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 1. Prometheus Middleware
app.add_middleware(PrometheusMiddleware)

# 2. Session Middleware (Required for Google Auth)
app.add_middleware(
    SessionMiddleware, 
    secret_key=settings.SECRET_KEY,
    session_cookie="procure_iq_session",
    max_age=3600 * 24 * 7  # 7 days
)

# 3. CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static Files & Templates
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# --- Authentication Dependencies ---

async def verify_google_auth(request: Request):
    """Dependency: Ensure user is logged in via Google."""
    user = request.session.get("user")
    if not user:
        if "text/html" in request.headers.get("accept", ""):
            # If browser request, redirect to login
            raise HTTPException(status_code=307, detail="Redirecting to login") 
        else:
             # If API request, 401
             raise HTTPException(status_code=401, detail="Authentication required")
    return user

async def verify_api_key_or_google(request: Request, x_api_key: str = Header(None)):
    """Allow access via EITHER Google Auth (Browser) OR API Key (Devices)."""
    # 1. Check Google Session
    user = request.session.get("user")
    if user:
        return {"type": "user", "data": user}
    
    # 2. Check API Key
    if x_api_key and x_api_key == settings.API_KEY:
         return {"type": "apikey", "data": "device"}
    
    # Fail
    if "text/html" in request.headers.get("accept", ""):
        raise HTTPException(status_code=307, detail="Redirecting to login")
    
    raise HTTPException(status_code=401, detail="Authentication required")

# --- Global Exception Handler for Redirects ---
@app.exception_handler(HTTPException)
async def auth_redirect_wrapper(request: Request, exc: HTTPException):
    if exc.status_code == 307 and exc.detail == "Redirecting to login":
        return RedirectResponse("/login")
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


# --- Routes ---

# Public Health Check (Railway monitoring)
@app.get("/health")
def health_check():
    """Health check endpoint for Railway / load balancers."""
    from .agent.worker import get_worker_state
    worker = get_worker_state()
    ai_provider = "openrouter" if os.environ.get("OPENROUTER_API_KEY") else (
        "gemini" if os.environ.get("GEMINI_API_KEY") else "rule_based"
    )
    return {
        "status": "ok",
        "ai_provider": ai_provider,
        "worker_status": worker.get("status", "unknown"),
        "base_url": settings.BASE_URL,
    }

# Public Routes
@app.get("/login")
def login_page(request: Request):
    """Login landing page (public)."""
    return templates.TemplateResponse("login.html", {"request": request})

app.include_router(auth.router)

@app.get("/health")
def health_check():
    """Service health check for Railway/monitoring."""
    return {"status": "healthy", "timestamp": datetime.datetime.now().isoformat()}

# Protected Dashboard Routes
@app.get("/", dependencies=[Depends(verify_google_auth)])
def read_root(request: Request):
    """Landing page (Protected)."""
    user = request.session.get("user")
    return templates.TemplateResponse("index.html", {
        "request": request,
        "api_key": settings.API_KEY, # Pass to frontend for JS calls
        "user": user
    })

@app.get("/settings", dependencies=[Depends(verify_google_auth)])
def settings_page(request: Request):
    """Settings page (Protected)."""
    user = request.session.get("user")
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "api_key": settings.API_KEY,
        "user": user
    })

@app.get("/inventory", dependencies=[Depends(verify_google_auth)])
def inventory_page(request: Request):
    """ERP-style Inventory Management page (Protected)."""
    user = request.session.get("user")
    return templates.TemplateResponse("inventory.html", {
        "request": request,
        "api_key": settings.API_KEY,
        "user": user
    })

@app.get("/invoice/{invoice_id}", dependencies=[Depends(verify_google_auth)])
def invoice_detail_page(invoice_id: int, request: Request, db: Session = Depends(get_db)):
    """Invoice detail page — three-way match visualization."""
    user = request.session.get("user")
    invoice = db.query(models.Invoice).filter(models.Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return templates.TemplateResponse("invoice_detail.html", {
        "request": request,
        "invoice": invoice,
        "api_key": settings.API_KEY,
        "user": user
    })

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return get_metrics()

# ── Gmail Invoice Agent API ───────────────────────────────────────────────────

@app.get("/api/gmail-invoices")
def list_gmail_invoices(limit: int = 50, db: Session = Depends(get_db)):
    """Return the most recent invoices detected from the owner's Gmail."""
    from .models import GmailInvoice
    invoices = (
        db.query(GmailInvoice)
        .order_by(GmailInvoice.received_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": inv.id,
            "subject": inv.subject,
            "sender": inv.sender,
            "amount": inv.amount,
            "invoice_number": inv.invoice_number,
            "received_at": inv.received_at.isoformat() if inv.received_at else None,
            "found_in_spam": inv.found_in_spam,
            "status": inv.status,
        }
        for inv in invoices
    ]

@app.patch("/api/gmail-invoices/{invoice_id}/status")
def update_gmail_invoice_status(invoice_id: int, body: dict, db: Session = Depends(get_db)):
    """Approve or reject a Gmail-detected invoice."""
    from .models import GmailInvoice
    inv = db.query(GmailInvoice).filter(GmailInvoice.id == invoice_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    new_status = body.get("status", "").upper()
    if new_status not in ("APPROVED", "REJECTED"):
        raise HTTPException(status_code=400, detail="status must be APPROVED or REJECTED")
    inv.status = new_status
    # Write audit trail entry
    trail = list(inv.audit_trail or [])
    trail.append({
        "t": datetime.datetime.utcnow().isoformat(),
        "a": new_status.lower(),
        "m": f"Manually marked {new_status} via dashboard"
    })
    inv.audit_trail = trail
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(inv, "audit_trail")
    db.commit()
    return {"success": True, "id": invoice_id, "status": inv.status}


@app.get("/api/alerts")
def get_stock_alerts(db: Session = Depends(get_db)):
    """
    Return live low-stock items directly from the inventory table.
    Polls every 5 s from the dashboard Stock Alerts panel.
    """
    from .models import InventoryItem

    # Use real DB column names (not the Python property aliases)
    low_items = (
        db.query(InventoryItem)
        .filter(InventoryItem.stock_quantity <= InventoryItem.reorder_level)
        .all()
    )

    results = []
    for item in low_items:
        qty = item.stock_quantity
        thr = item.reorder_level
        pct = round(qty / max(thr, 1) * 100)
        urgency = "CRITICAL" if qty == 0 else ("HIGH" if pct <= 25 else "LOW")
        results.append({
            "id":     item.id,
            "status": "PENDING",        # renderAlerts filters on this
            "payload": {
                "item_id":     item.id,
                "item_name":   item.product_name,
                "current_qty": qty,
                "threshold":   thr,
                "reorder_qty": item.reorder_quantity,
                "unit_price":  item.cost_price,
                "sku":         item.sku or "—",
                "urgency":     urgency,
                "pct_remaining": pct,
                "message": (
                    f"Only {qty} unit(s) left "
                    f"(threshold: {thr}). "
                    f"Suggested reorder: {item.reorder_quantity} units."
                ),
            },
        })

    return results


@app.post("/api/alerts/trigger")
async def trigger_stock_check(db: Session = Depends(get_db)):
    """Manually fire the stock alert check (e.g. from dashboard button)."""
    from .services.alert_service import process_stock_alerts
    result = await process_stock_alerts(db)
    return {"triggered": True, **result}


# ── Agent Status ──────────────────────────────────────────────────────────────


@app.get("/api/agent-status")
def get_agent_status():
    """Return current state of all background agents."""
    from .agent.worker import get_worker_state  # imported lazily
    try:
        worker = get_worker_state()
    except Exception:
        worker = {"status": "unknown"}
    return {
        "gmail_agent": agent_state,
        "inventory_agent": worker,
    }


# ── Analytics ─────────────────────────────────────────────────────────────────

@app.get("/api/analytics")
def get_analytics(db: Session = Depends(get_db)):
    """Spend analytics: vendor breakdown, approval rates, invoice counts."""
    from .models import GmailInvoice
    from sqlalchemy import func
    import datetime as dt

    invoices = db.query(GmailInvoice).all()
    total = len(invoices)
    approved = sum(1 for i in invoices if i.status == "APPROVED")
    rejected  = sum(1 for i in invoices if i.status == "REJECTED")
    pending   = sum(1 for i in invoices if i.status == "PENDING_REVIEW")
    total_spend = sum(i.amount or 0 for i in invoices if i.status == "APPROVED")

    # Spend by vendor
    vendor_spend: dict = {}
    for inv in invoices:
        key = inv.vendor_name or inv.sender or "Unknown"
        vendor_spend[key] = vendor_spend.get(key, 0) + (inv.amount or 0)
    top_vendors = sorted(vendor_spend.items(), key=lambda x: x[1], reverse=True)[:10]

    # Last 7 days volume
    week_ago = dt.datetime.utcnow() - dt.timedelta(days=7)
    weekly = sum(1 for i in invoices if i.received_at and i.received_at >= week_ago)

    return {
        "total_invoices": total,
        "approved": approved,
        "rejected": rejected,
        "pending": pending,
        "total_approved_spend": round(total_spend, 2),
        "approval_rate": round(approved / total * 100, 1) if total else 0,
        "invoices_last_7_days": weekly,
        "top_vendors": [{"vendor": k, "spend": round(v, 2)} for k, v in top_vendors],
    }


# --- Database & Security ---
try:
    models.Base.metadata.create_all(bind=engine)
    print("[STARTUP] Database tables created successfully")
except Exception as e:
    print(f"[STARTUP] WARNING: Database connection failed: {e}")
    print("[STARTUP] App will start but database features won't work until DATABASE_URL is fixed")

# API Key Logic (for server logs)
if not settings.API_KEY:
    import secrets
    settings.API_KEY = secrets.token_urlsafe(32)
    print(f"\n[WARNING] No API_KEY set in .env - Generated random key: {settings.API_KEY}")



# --- API Routes ---

# AI Health Check (Protected)
@app.get("/api/ai-health", dependencies=[Depends(verify_api_key_or_google)])
async def ai_health_check():
    """AI health and metrics."""
    from .agent.ai_client import get_ai_client
    client = get_ai_client()
    health = await client.health_check()
    return {
        "status": "ok",
        "services": health,
        "timestamp": datetime.datetime.now().isoformat()
    }

@app.get("/api/ai-status", dependencies=[Depends(verify_api_key_or_google)])
async def ai_status():
    """Public endpoint returning current AI provider for dashboard badge."""
    from .agent.ai_client import get_ai_client
    client = get_ai_client()
    
    provider = "No AI Configured"
    detail = "Rule-based fallback"
    status = "inactive"
    
    if hasattr(client, 'client') and client.client:
        provider = "Gemini 2.0 Flash"
        detail = "OpenRouter API"
        status = "active"
    elif hasattr(client, 'gemini_model') and client.gemini_model:
        provider = "Gemini (Direct)"
        detail = "Google AI SDK"
        status = "active"
    elif hasattr(client, 'openai_client') and client.openai_client:
        provider = "GPT-4o"
        detail = "OpenAI API"
        status = "active"
    
    return {
        "provider": provider,
        "detail": detail,
        "status": status,
        "model": getattr(client, 'primary_model', 'unknown')
    }

# --- Include Modules ---
from .api import invoices, owner_actions, approval_routes, analytics_routes, erp_management
from .api import credentials_routes

# Protect API routes with dual auth (Key OR Session)
app.include_router(invoices.router, prefix="/api", dependencies=[Depends(verify_api_key_or_google)])
app.include_router(owner_actions.router, dependencies=[Depends(verify_api_key_or_google)])
app.include_router(analytics_routes.router, dependencies=[Depends(verify_api_key_or_google)])
app.include_router(erp_management.router, dependencies=[Depends(verify_api_key_or_google)])

# Credential management (auth checked inside each route)
app.include_router(credentials_routes.router)

# Public Token-based Approval Routes (No Auth required as they use secure tokens)
app.include_router(approval_routes.router, prefix="/api", tags=["approvals"])

# --- Database Seeding ---
def seed_inventory():
    db = SessionLocal()
    if db.query(models.InventoryItem).count() < 5:
        db.query(models.InventoryItem).delete()
        items = [
            models.InventoryItem(name="MacBook Pro M3", brand="Apple", quantity=45, reorder_threshold=50, reorder_quantity=10, unit_price=1999.0, sku="APL-MBP-M3"),
            models.InventoryItem(name="ThinkPad X1 Carbon", brand="Lenovo", quantity=3, reorder_threshold=10, reorder_quantity=5, unit_price=1499.0, sku="LEN-X1C-G11"),
            models.InventoryItem(name="Logitech MX Master 3S", brand="Logitech", quantity=55, reorder_threshold=50, reorder_quantity=20, unit_price=99.0, sku="LOG-MXM-3S"),
            models.InventoryItem(name="Dell UltraSharp 27", brand="Dell", quantity=8, reorder_threshold=15, reorder_quantity=10, unit_price=499.0, sku="DEL-U2723QE"),
            models.InventoryItem(name="Keychron K2 V2", brand="Keychron", quantity=2, reorder_threshold=20, reorder_quantity=15, unit_price=89.0, sku="KCY-K2-V2")
        ]
        db.add_all(items)
        db.commit()
    db.close()

seed_inventory()

# Seed ERP data
from .init_db import seed_erp_data
try:
    _db = SessionLocal()
    seed_erp_data(_db)
    _db.close()
except Exception as e:
    print(f"[WARN] ERP seed: {e}")

