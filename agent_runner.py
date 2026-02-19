#!/usr/bin/env python3
"""
Procure-IQ Standalone Agent Runner

Start the autonomous agent WITHOUT the FastAPI UI:
    python agent_runner.py

The agent will:
  - Initialize the database and seed data
  - Poll for PENDING events continuously
  - Process invoices autonomously (AI matching + three-way match)
  - Learn vendor aliases from approved invoices
  - Monitor stock levels and trigger alerts

To test autonomy:
  1. Start: python agent_runner.py
  2. In another terminal, insert an event:
     python -c "
     import sys; sys.path.insert(0, '.')
     from app.database import SessionLocal
     from app import models
     db = SessionLocal()
     e = models.Event(
         event_type='INVOICE_RECEIVED',
         payload={'invoiceNumber': 'INV-TEST-001', 'vendorName': 'Acme Corp', 'invoiceAmount': 1500.00},
         status='PENDING'
     )
     db.add(e); db.commit()
     print(f'Event {e.id} created. Agent will pick it up.')
     "
  3. Watch the agent logs — it will process the invoice automatically.
"""

import os
import sys
import logging

# Setup path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)-15s | %(levelname)-5s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Ensure database tables exist and seed data
from app.database import engine
from app.models import Base
Base.metadata.create_all(bind=engine)

from app.database import SessionLocal
from app.init_db import seed_erp_data

try:
    db = SessionLocal()
    seed_erp_data(db)
    db.close()
    logging.getLogger("AgentRunner").info("Database initialized and seeded.")
except Exception as e:
    logging.getLogger("AgentRunner").warning(f"Seed warning: {e}")

# Start the autonomous agent loop
if __name__ == "__main__":
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║       PROCURE-IQ AUTONOMOUS AGENT (Standalone)         ║")
    print("║                                                        ║")
    print("║  The agent is running WITHOUT the UI.                  ║")
    print("║  It will poll for events and process invoices.         ║")
    print("║                                                        ║")
    print("║  Press Ctrl+C to stop.                                 ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()
    
    from app.agent.worker import start_agent_loop
    start_agent_loop()
