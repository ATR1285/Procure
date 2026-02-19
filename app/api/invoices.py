"""
Invoice API Routes — Approve, Reject, List

LEARNING: On approval, the system auto-learns vendor aliases
via ERPAdapter so future invoices from the same vendor variation
get higher confidence automatically.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from typing import List
from .. import crud, models, schemas
from ..database import get_db
import logging

router = APIRouter()
logger = logging.getLogger("InvoiceAPI")

@router.get("/invoices", response_model=List[schemas.Invoice])
def read_invoices(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    invoices = crud.get_invoices(db, skip=skip, limit=limit)
    return invoices

@router.get("/invoices/{invoice_id}", response_model=schemas.Invoice)
def read_invoice(invoice_id: int, db: Session = Depends(get_db)):
    db_invoice = crud.get_invoice(db, invoice_id=invoice_id)
    if db_invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return db_invoice

@router.post("/invoices/{invoice_id}/approve")
def approve_invoice(invoice_id: int, db: Session = Depends(get_db)):
    """
    Approve an invoice. Triggers AUTOMATIC learning:
    
    If the invoice has a raw_vendor name that differs from the matched
    vendor's canonical name, the system learns this alias so future
    invoices with the same variation get 100% confidence instantly.
    
    Learning flow:
    1. Human approves invoice (this endpoint)
    2. System extracts raw_vendor from invoice.extracted_data
    3. System looks up the matched vendor's canonical name via ERPAdapter
    4. If raw_vendor ≠ canonical_name → store alias via ERPAdapter
    5. Next invoice with same raw_vendor → alias hit → 100% confidence
    """
    from ..services.erp_adapter import erp_adapter
    
    db_invoice = crud.get_invoice(db, invoice_id=invoice_id)
    if not db_invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    db_invoice.status = "APPROVED"
    
    # ── AUTOMATIC LEARNING ──────────────────────────────────────
    # Extract the raw vendor name from invoice data
    raw_vendor = None
    if db_invoice.extracted_data:
        raw_vendor = db_invoice.extracted_data.get("raw_vendor")
    
    if raw_vendor and db_invoice.vendor_id:
        # Get the canonical vendor name via ERP Adapter (not direct DB)
        vendor_info = erp_adapter.get_vendor_by_id(db_invoice.vendor_id)
        canonical_name = vendor_info["name"] if vendor_info else None
        
        if canonical_name and raw_vendor.lower().strip() != canonical_name.lower().strip():
            # Raw name differs from canonical — LEARN THIS ALIAS
            stored = erp_adapter.store_vendor_alias(
                alias_name=raw_vendor,
                vendor_id=db_invoice.vendor_id,
                invoice_id=invoice_id
            )
            
            if stored:
                logger.info(f"[LEARNING] Learning alias: '{raw_vendor}' → '{canonical_name}' (vendor_id={db_invoice.vendor_id})")
                
                # Record learning in audit trail
                if not db_invoice.audit_trail:
                    db_invoice.audit_trail = []
                db_invoice.audit_trail.append({
                    "t": "learned",
                    "m": f"Learned alias '{raw_vendor}' → '{canonical_name}' for future autonomous matching"
                })
                flag_modified(db_invoice, "audit_trail")
            else:
                logger.info(f"[LEARNING] Alias '{raw_vendor}' already known")
        else:
            logger.info(f"[LEARNING] No new alias needed — raw_vendor matches canonical name")
    
    db.commit()
    
    return {
        "status": "success",
        "message": f"Invoice {invoice_id} approved. Learning applied." if raw_vendor else f"Invoice {invoice_id} approved."
    }

@router.post("/invoices/{invoice_id}/reject")
def reject_invoice(invoice_id: int, db: Session = Depends(get_db)):
    db_invoice = crud.get_invoice(db, invoice_id=invoice_id)
    if not db_invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    db_invoice.status = "REJECTED"
    db.commit()
    return {"status": "success"}


