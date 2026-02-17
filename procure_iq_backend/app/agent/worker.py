import time
import datetime
import asyncio
import logging
from sqlalchemy.orm import Session
from ..database import SessionLocal
from .. import models

logger = logging.getLogger(__name__)

def start_agent_loop():
    """
    Autonomous agent loop with exponential backoff and stock monitoring.
    
    Processes:
    1. Pending events (invoice matching, etc.)
    2. Stock alerts (every 60 seconds)
    
    Features:
    - Exponential backoff (2s to 30s) when idle
    - Graceful shutdown on KeyboardInterrupt
    - Comprehensive error handling
    - Detailed logging with timestamps
    """
    db = SessionLocal()
    wait_time = 2  # Initial wait time in seconds
    last_stock_check = 0  # Timestamp of last stock check
    STOCK_CHECK_INTERVAL = 60  # Check stock every 60 seconds
    
    print(f"[{datetime.datetime.now()}] Agent loop started")
    
    while True:
        # Create a new session for each loop iteration to ensure it's fresh
        db = SessionLocal()
        try:
            # 1. Update worker heartbeat
            try:
                status = db.query(models.SystemStatus).filter(models.SystemStatus.service_name == "worker").first()
                if not status:
                    status = models.SystemStatus(service_name="worker", status="healthy")
                    db.add(status)
                status.last_heartbeat = datetime.datetime.now() # Use datetime.datetime.now()
                status.status = "healthy"
                db.commit()
            except Exception as e:
                logger.error(f"Failed to update worker heartbeat: {e}")
                db.rollback()

            # 2. Process events
            logger.info("Worker: Checking for new events...")

            current_time = time.time()
            
            # 1. Process pending events (invoice matching, etc.)
            events = db.query(models.Event).filter(models.Event.status == 'pending').all()
            
            if events:
                # Reset wait time if events were found
                wait_time = 2
                
                for event in events:
                    print(f"[{datetime.datetime.now()}] Processing event ID {event.id} of type {event.event_type}")
                    
                    try:
                        # Process event based on type
                        if event.event_type == "INVOICE_RECEIVED":
                            from ..agent.matcher import process_invoice_match
                            process_invoice_match(db, event.payload)
                        
                        # Mark as completed
                        event.status = 'completed'
                        event.processed_at = datetime.datetime.now()
                        db.commit()
                        
                        print(f"[{datetime.datetime.now()}] Event {event.id} completed successfully")
                        
                    except Exception as e:
                        print(f"[{datetime.datetime.now()}] ERROR processing event {event.id}: {e}")
                        event.status = 'failed'
                        db.commit()
            
            # 2. Check stock alerts (every 60 seconds)
            if current_time - last_stock_check >= STOCK_CHECK_INTERVAL:
                print(f"[{datetime.datetime.now()}] Running stock alert check...")
                
                try:
                    from ..services.alert_service import process_stock_alerts
                    
                    # Run async function in sync context
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    result = loop.run_until_complete(process_stock_alerts(db))
                    loop.close()
                    
                    if result.get('low_stock_items', 0) > 0:
                        print(f"[{datetime.datetime.now()}] Stock alerts: {result['low_stock_items']} items, "
                              f"email={result['email_sent']}, sms={result['sms_sent']}")
                    
                    last_stock_check = current_time
                    
                except Exception as e:
                    print(f"[{datetime.datetime.now()}] ERROR in stock alert check: {e}")
                    last_stock_check = current_time  # Don't retry immediately
            
            # 3. Check for invoice emails (every 5 minutes)
            EMAIL_CHECK_INTERVAL = 300  # 5 minutes
            if 'last_email_check' not in locals():
                last_email_check = 0
            
            if current_time - last_email_check >= EMAIL_CHECK_INTERVAL:
                print(f"[{datetime.datetime.now()}] Checking for invoice emails...")
                
                try:
                    from ..services.email_service import EmailIngestionService
                    
                    # Initialize email service
                    email_service = EmailIngestionService()
                    
                    # Fetch latest invoices
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    invoices = loop.run_until_complete(email_service.fetch_latest_invoices())
                    loop.close()
                    
                    if invoices:
                        print(f"[{datetime.datetime.now()}] Found {len(invoices)} invoice emails")
                        
                        # Create events for each invoice
                        for invoice in invoices:
                            # Create INVOICE_RECEIVED event
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
                                status="pending"
                            )
                            db.add(event)
                        
                        db.commit()
                        print(f"[{datetime.datetime.now()}] Created {len(invoices)} invoice events")
                    
                    last_email_check = current_time
                    
                except Exception as e:
                    print(f"[{datetime.datetime.now()}] ERROR in email check: {e}")
                    last_email_check = current_time  # Don't retry immediately
            
            # 4. Exponential backoff when idle
            if not events:
                print(f"[{datetime.datetime.now()}] No events found. Waiting for {wait_time} seconds...")
                time.sleep(wait_time)
                wait_time = min(wait_time * 2, 30)  # Double wait time, max 30 seconds
            else:
                time.sleep(2)  # Small delay between event batches

        except KeyboardInterrupt:
            print(f"\n[{datetime.datetime.now()}] Agent loop stopped cleanly.")
            break
            
        except Exception as e:
            print(f"[{datetime.datetime.now()}] ERROR in agent loop: {e}")
            
            # Log error to database
            try:
                error_log = models.Event(
                    event_type="AGENT_ERROR",
                    payload={"error": str(e), "timestamp": datetime.datetime.now().isoformat()},
                    status="failed"
                )
                db.add(error_log)
                db.commit()
            except:
                pass  # Don't crash if logging fails
            
            time.sleep(wait_time)  # Wait before retrying after error
            wait_time = min(wait_time * 2, 30)  # Continue exponential backoff
    
    db.close()
    print(f"[{datetime.datetime.now()}] Agent loop terminated")
