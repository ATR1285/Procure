import asyncio
import logging
from app.services.email_service import EmailIngestionService
from app.database import SessionLocal
from app import models

# Configure logging to see output in console
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')

async def run_manual_scan():
    print("\n" + "="*50)
    print("  PROCURE-IQ — Manual Gmail Invoice Scan")
    print("="*50)
    
    service = EmailIngestionService()
    
    if not service.gmail_service:
        print("\n[!] ERROR: Gmail service not initialized.")
        print("    Please run: python gmail_auth_setup.py")
        return

    print("\nScanning Inbox and Spam for invoices...")
    invoices = await service.fetch_latest_invoices(max_results=5)
    
    if not invoices:
        print("\n[i] No new invoices found in the last 24 hours.")
    else:
        print(f"\n[+] Found {len(invoices)} invoice(s):")
        db = SessionLocal()
        try:
            for inv in invoices:
                print(f"    - From: {inv['from']}")
                print(f"      Subject: {inv['subject']}")
                print(f"      Vendor: {inv['vendor_name']} | Amount: {inv['amount']}")
                
                # Check if we should create an event (similar to worker.py)
                event = models.Event(
                    event_type="INVOICE_RECEIVED",
                    payload={
                        "invoiceNumber": inv['invoice_number'],
                        "vendorName": inv['vendor_name'],
                        "invoiceAmount": inv['amount'],
                        "source": "manual_scan",
                        "email_subject": inv['subject'],
                        "email_from": inv['from'],
                        "extraction_confidence": inv['confidence']
                    },
                    status="PENDING"
                )
                db.add(event)
            db.commit()
            print("\n[V] Events created in database for processing.")
        finally:
            db.close()

    print("\n" + "="*50 + "\n")

if __name__ == "__main__":
    asyncio.run(run_manual_scan())
