import time
import logging
from sqlalchemy.orm import Session
from ..database import SessionLocal
from .. import crud, models
from .matcher import process_invoice_match

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AutonomousAgent")

def start_agent_loop():
    """
    Continuous background loop that polls the Event table.
    This is the core 'Autonomous Agent' requirement.
    """
    logger.info("Autonomous Agent Loop Started")
    
    while True:
        db = SessionLocal()
        try:
            # Poll for pending events
            # 1. Check Inventory (Every loop)
            from .inventory_manager import check_inventory_levels
            check_inventory_levels(db)
            
            # 2. Poll Real Emails (New)
            from ..services.email_service import EmailIngestionService
            email_svc = EmailIngestionService()
            new_emails = email_svc.fetch_latest_invoices()
            for em in new_emails:
                logger.info(f"📧 New Invoice Email Detected: {em['subject']}")
                # Trigger a real event in the DB
                new_event = models.Event(
                    event_type="INVOICE_RECEIVED",
                    payload={
                        "invoiceNumber": f"MAIL-{em['date']}", # Temporary ID
                        "vendorName": em['from'], # Raw from email
                        "invoiceAmount": 0.0, # Will be extracted by AI in next step
                        "raw_text": em['body'] # Full text for AI analysis
                    }
                )
                db.add(new_event)
                db.commit()

            # 3. Process Pending Events (Invoices, Approvals, etc.)
            # Fetch all pending events to process them in a loop
            pending_events = crud.get_pending_events(db)
            
            for event in pending_events:
                logger.info(f"Processing event: {event.event_type} (ID: {event.id})")
                
                # Update status to processing
                event.status = "PROCESSING"
                db.commit()
                
                try:
                    if event.event_type == "INVOICE_RECEIVED":
                        # Execute matching logic
                        process_invoice_match(db, event.payload)
                    
                    elif event.event_type == "VENDOR_LEARNED":
                        # Handle ontology update
                        logger.info("Updating vendor ontology based on human approval")
                        # (Logic to update VendorAlias table)
                    
                    event.status = "COMPLETED"
                except Exception as e:
                    logger.error(f"Error processing event {event.id}: {str(e)}")
                    event.status = "FAILED"
                
                db.commit()
                
        except Exception as e:
            logger.error(f"Agent loop error: {str(e)}")
        finally:
            db.close()
            
        # Poll interval
        time.sleep(5)
