from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from .. import crud, models, schemas
from ..database import get_db

router = APIRouter()

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
def approve_invoice(invoice_id: int, vendor_id: int = None, new_alias: str = None, db: Session = Depends(get_db)):
    db_invoice = crud.get_invoice(db, invoice_id=invoice_id)
    if not db_invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    db_invoice.status = "APPROVED"
    
    # LEARNING LOOP: If a new alias is provided, learn it
    if new_alias and vendor_id:
        existing = db.query(models.VendorAlias).filter(models.VendorAlias.alias_name == new_alias).first()
        if not existing:
            alias = models.VendorAlias(
                alias_name=new_alias,
                vendor_id=vendor_id,
                learned_from_invoice_id=invoice_id
            )
            db.add(alias)
            db_invoice.audit_trail.append({"t": "learned", "m": f"Learned alias '{new_alias}' for vendor ID {vendor_id}"})
    
    db.commit()
    return {"status": "success"}

@router.post("/invoices/{invoice_id}/reject")
def reject_invoice(invoice_id: int, db: Session = Depends(get_db)):
    db_invoice = crud.get_invoice(db, invoice_id=invoice_id)
    if not db_invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    db_invoice.status = "REJECTED"
    db.commit()
    return {"status": "success"}
