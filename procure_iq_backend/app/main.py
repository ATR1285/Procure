from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import threading
import time
import os
import datetime

from . import models, schemas, crud
from .database import SessionLocal, engine
from .agent.worker import start_agent_loop

# Initialize database
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="ProcureIQ Autonomous Backend")

# Setup directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared Database Session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.on_event("startup")
async def startup_event():
    # Start the autonomous agent loop in a separate thread
    threading.Thread(target=start_agent_loop, daemon=True).start()

@app.get("/api/system-status")
def get_status():
    return {"status": "ok", "agent": "active", "engine": "FastAPI"}

from .api import invoices, simulation, owner_actions

# Include routers
app.include_router(invoices.router, prefix="/api")
app.include_router(simulation.router, prefix="/api")
app.include_router(owner_actions.router) # Prefix is handled inside router or here

# Seed some inventory for testing if empty
def seed_inventory():
    db = SessionLocal()
    if db.query(models.Inventory).count() == 0:
        items = [
            models.Inventory(item_name="Desk Lamp", quantity=45, limit_threshold=50),
            models.Inventory(item_name="Office Chair", quantity=55, limit_threshold=50),
            models.Inventory(item_name="USB Hub", quantity=10, limit_threshold=50)
        ]
        db.add_all(items)
        db.commit()
    db.close()

seed_inventory()

@app.get("/")
def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
