from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import SessionLocal
from .. import models, schemas
from ..services.notifications import send_email_to_supplier
import datetime

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/api/inventory")
def get_inventory(db: Session = Depends(get_db)):
    return db.query(models.InventoryItem).all()

@router.post("/api/owner/approve-refill/{event_id}")
def approve_refill(event_id: int, db: Session = Depends(get_db)):
    """
    Owner approvals a refill request. 
    The agent then sends the mail to the supplier.
    """
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    item_id = event.payload.get("item_id")
    item = db.query(models.InventoryItem).filter(models.InventoryItem.id == item_id).first()
    
    if item:
        # Simulate replenishing or placing order
        vendor = db.query(models.Vendor).filter(models.Vendor.id == item.supplier_id).first()
        vendor_email = vendor.email if vendor else "supplier@example.com"
        
        # Trigger Mail to Supplier
        send_email_to_supplier(vendor_email, item.name, item.reorder_quantity)
        
        # Update Event
        event.status = "COMPLETED"
        event.processed_at = datetime.datetime.utcnow()
        
        # Update Inventory (Simulate refill incoming)
        # In a real app, this would wait for a packing slip event
        item.last_checked = datetime.datetime.utcnow()
        # For demonstration: replenish the stock
        item.quantity += item.reorder_quantity
        
        db.commit()
        return {"status": "success", "message": f"Order sent to {vendor_email} and inventory updated."}
    
    return {"status": "error", "message": "Item not found"}

@router.get("/api/alerts")
def get_alerts(db: Session = Depends(get_db)):
    return db.query(models.Event).filter(models.Event.event_type == "STOCK_ALERT").all()
