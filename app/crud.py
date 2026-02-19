from sqlalchemy.orm import Session
from . import models, schemas
import datetime

def get_invoice(db: Session, invoice_id: int):
    return db.query(models.Invoice).filter(models.Invoice.id == invoice_id).first()

def get_invoices(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Invoice).order_by(models.Invoice.id.desc()).offset(skip).limit(limit).all()

def create_invoice(db: Session, invoice: schemas.InvoiceCreate):
    db_invoice = models.Invoice(**invoice.dict())
    db.add(db_invoice)
    db.commit()
    db.refresh(db_invoice)
    return db_invoice

def create_event(db: Session, event_type: str, payload: dict):
    db_event = models.Event(event_type=event_type, payload=payload, status="PENDING")
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event

def get_pending_events(db: Session):
    return db.query(models.Event).filter(models.Event.status == "PENDING").all()

def mark_event_processed(db: Session, event_id: int):
    db_event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if db_event:
        db_event.status = "COMPLETED"
        db_event.processed_at = datetime.datetime.utcnow()
        db.commit()
