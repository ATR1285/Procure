"""
Procure-IQ Autonomous Agent Loop

ENTERPRISE DATABASE RULES:
- Fresh session per poll cycle (no stale reads)
- Event locking: PENDING → PROCESSING → DONE
- Immediate commits after every state change
- Agent sees DB changes from UI/API instantly
- UI sees agent changes via 5-second polling

The agent IS the background process.
It works whether the UI is running or not.
"""

import time
import datetime
import asyncio
import logging
from sqlalchemy.orm import Session
from ..database import SessionLocal
from .. import models

logger = logging.getLogger("Agent")

def start_agent_loop():
    """
    Autonomous agent loop — single source of truth is the database.
    
    Every poll cycle:
    1. Opens a FRESH db session (sees latest committed state)
    2. Claims PENDING events by setting status → PROCESSING (atomic lock)
    3. Processes each event
    4. Sets status → DONE or FAILED
    5. Closes session
    
    This ensures:
    - No double-processing (PENDING→PROCESSING lock)
    - Agent sees UI/API writes immediately
    - UI sees agent writes immediately (via polling)
    """
    wait_time = 2
    last_stock_check = 0
    last_email_check = 0
    STOCK_CHECK_INTERVAL = 60
    EMAIL_CHECK_INTERVAL = 300
    
    logger.info("=" * 60)
    logger.info("[AGENT] Procure-IQ Autonomous Agent STARTED")
    logger.info(f"[AGENT] Timestamp: {datetime.datetime.now().isoformat()}")
    logger.info(f"[AGENT] Database: Single shared SQLite (WAL mode)")
    logger.info(f"[AGENT] Poll interval: {wait_time}s (backoff to 30s when idle)")
    logger.info("=" * 60)
    
    while True:
        # FRESH session every cycle — always sees latest committed state
        db = SessionLocal()
        try:
            # ── Heartbeat ──────────────────────────────────────
            try:
                status = db.query(models.SystemStatus).filter(
                    models.SystemStatus.service_name == "agent"
                ).first()
                if not status:
                    status = models.SystemStatus(service_name="agent", status="healthy")
                    db.add(status)
                status.last_heartbeat = datetime.datetime.now()
                status.status = "healthy"
                db.commit()
            except Exception as e:
                logger.error(f"[AGENT] Heartbeat failed: {e}")
                db.rollback()

            # ── Poll for PENDING events ────────────────────────
            current_time = time.time()
            logger.info(f"[AGENT] Polling for PENDING events...")
            
            events = db.query(models.Event).filter(
                models.Event.status == 'PENDING'
            ).all()
            
            if events:
                wait_time = 2  # Reset backoff
                logger.info(f"[AGENT] Found {len(events)} PENDING event(s)")
                
                for event in events:
                    # ── LOCK: Claim event (PENDING → PROCESSING) ──
                    event.status = 'PROCESSING'
                    db.commit()
                    logger.info(f"[AGENT] ── Locked event {event.id} (PROCESSING) ──")
                    
                    try:
                        if event.event_type == "INVOICE_RECEIVED":
                            vendor = event.payload.get('vendorName', 'Unknown')
                            amount = event.payload.get('invoiceAmount', 0)
                            logger.info(f"[AGENT] Processing INVOICE_RECEIVED: vendor='{vendor}', amount={amount}")
                            
                            from ..agent.matcher import process_invoice_match
                            process_invoice_match(db, event.payload)
                            
                            logger.info(f"[AGENT] ✓ Invoice match computed, DB updated")
                        
                        # ── DONE: Mark event complete ──────────────
                        event.status = 'DONE'
                        event.processed_at = datetime.datetime.now()
                        db.commit()
                        logger.info(f"[AGENT] ✓ Event {event.id} → DONE (committed)")
                        
                    except Exception as e:
                        logger.error(f"[AGENT] ✗ Event {event.id} FAILED: {e}")
                        event.status = 'FAILED'
                        db.commit()
            else:
                logger.debug(f"[AGENT] No PENDING events (backoff: {wait_time}s)")
            
            # ── Stock alerts ───────────────────────────────────
            if current_time - last_stock_check >= STOCK_CHECK_INTERVAL:
                logger.info(f"[AGENT] Running stock alert check...")
                try:
                    from ..services.alert_service import process_stock_alerts
                    
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    result = loop.run_until_complete(process_stock_alerts(db))
                    loop.close()
                    
                    if result.get('low_stock_items', 0) > 0:
                        logger.info(f"[AGENT] Stock alerts: {result['low_stock_items']} items flagged")
                    last_stock_check = current_time
                except Exception as e:
                    logger.error(f"[AGENT] Stock alert error: {e}")
                    last_stock_check = current_time
            
            # ── Email ingestion ────────────────────────────────
            if current_time - last_email_check >= EMAIL_CHECK_INTERVAL:
                logger.info(f"[AGENT] Checking for invoice emails...")
                try:
                    from ..services.email_service import EmailIngestionService
                    email_service = EmailIngestionService()
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    invoices = loop.run_until_complete(email_service.fetch_latest_invoices())
                    loop.close()
                    
                    if invoices:
                        logger.info(f"[AGENT] Found {len(invoices)} invoice emails")
                        for invoice in invoices:
                            event = models.Event(
                                event_type="INVOICE_RECEIVED",
                                payload={
                                    "invoiceNumber": invoice['invoice_number'],
                                    "vendorName": invoice['vendor_name'],
                                    "invoiceAmount": invoice['amount'],
                                    "raw_text": invoice['body'],
                                    "source": "email",
                                    "email_subject": invoice['subject'],
                                    "email_from": invoice['from'],
                                    "email_date": invoice['date'],
                                    "extraction_confidence": invoice['confidence']
                                },
                                status="PENDING"
                            )
                            db.add(event)
                        db.commit()
                        logger.info(f"[AGENT] Created {len(invoices)} PENDING events from email")
                    last_email_check = current_time
                except Exception as e:
                    logger.error(f"[AGENT] Email check error: {e}")
                    last_email_check = current_time
            
            # ── Backoff ────────────────────────────────────────
            if not events:
                time.sleep(wait_time)
                wait_time = min(wait_time * 2, 30)
            else:
                time.sleep(2)

        except KeyboardInterrupt:
            logger.info(f"\n[AGENT] Shutdown requested. Agent stopped cleanly.")
            break
        except Exception as e:
            logger.error(f"[AGENT] Loop error: {e}")
            try:
                error_log = models.Event(
                    event_type="AGENT_ERROR",
                    payload={"error": str(e), "timestamp": datetime.datetime.now().isoformat()},
                    status="FAILED"
                )
                db.add(error_log)
                db.commit()
            except:
                pass
            time.sleep(wait_time)
            wait_time = min(wait_time * 2, 30)
        finally:
            # ALWAYS close the session — next cycle gets a fresh one
            db.close()
    
    logger.info(f"[AGENT] Procure-IQ Autonomous Agent TERMINATED")
