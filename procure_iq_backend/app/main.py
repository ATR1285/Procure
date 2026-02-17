"""
Procure-IQ Main Application

Central entry point for the FastAPI backend.
Integrates security, AI monitoring (Prometheus + Sentry), background workers, 
and all API modules.
"""

import os
import sys
import time
import secrets
import threading
import datetime
import logging

from fastapi import FastAPI, Depends, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

# Add parent directory to path for config import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings
from . import models, schemas
from .database import SessionLocal, engine
from .models import Base
from .agent.worker import start_agent_loop

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

# --- App Initialization ---
app = FastAPI(
    title="Procure-IQ API",
    version="2.0.0",
    description="Intelligent Autonomous Procurement System"
)

# Prometheus Middleware (Must be before# Prometheus Metrics
app.add_middleware(PrometheusMiddleware)



# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static Files & Templates
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

@app.get("/")
def read_root(request: Request):
    """Landing page."""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "api_key": API_KEY
    })

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return get_metrics()

# --- Database & Security ---
models.Base.metadata.create_all(bind=engine)

# API Key Authentication Logic
API_KEY = settings.API_KEY
if not API_KEY:
    import secrets
    API_KEY = secrets.token_urlsafe(32)
    print(f"\n[WARNING] No API_KEY set in .env - Generated random key:")
    print(f"[KEY] API Key: {API_KEY}")
    print(f"[SETTINGS] Add this to your .env file: API_KEY={API_KEY}\n")
else:
    print(f"[INFO] API authentication enabled. Key begins with: {API_KEY[:4]}...")


def verify_api_key(x_api_key: str = Header(None)):
    """Dependency for API key verification."""
    # Debug print for identifying auth issues
    print(f"DEBUG AUTH: Received header='{x_api_key}', Expected='{API_KEY}'")
    if x_api_key != API_KEY:
        print(f"AUTH FAILED: Mismatch between {x_api_key} and {API_KEY}")
        raise HTTPException(
            status_code=401,
            detail=f"Invalid or missing API key. Include X-API-Key header."
        )
    return x_api_key



# --- Event Handlers ---
@app.on_event("startup")
async def startup_event():
    # Start the autonomous agent loop in a separate thread
    threading.Thread(target=start_agent_loop, daemon=True).start()

# --- API Routes ---


# AI Health Check

@app.get("/api/ai-health", dependencies=[Depends(verify_api_key)])
async def ai_health_check():
    """AI health and metrics."""
    from .agent.ai_client import get_ai_client
    client = get_ai_client()
    health = await client.health_check()
    stats = client.get_stats()
    return {
        "status": "ok",
        "services": health,
        "usage": stats,
        "timestamp": datetime.datetime.now().isoformat()
    }

# --- Include Modules ---
from .api import invoices, simulation, owner_actions, approval_routes, analytics_routes

app.include_router(invoices.router, prefix="/api", dependencies=[Depends(verify_api_key)])
app.include_router(simulation.router, prefix="/api", dependencies=[Depends(verify_api_key)])
app.include_router(owner_actions.router, dependencies=[Depends(verify_api_key)])
app.include_router(analytics_routes.router, dependencies=[Depends(verify_api_key)])

# Public Approval Routes (Token-based)
app.include_router(approval_routes.router, prefix="/api/approval")

# --- Database Seeding ---
def seed_inventory():
    db = SessionLocal()
    # Check if we need to re-seed due to schema changes or empty table
    if db.query(models.InventoryItem).count() < 5:
        # Clear existing items to ensure branding is applied
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
