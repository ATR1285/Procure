from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from ..database import SessionLocal
from .. import models, schemas
from ..services.notifications import send_email_to_supplier, send_sms_to_owner, send_whatsapp_to_owner
import datetime
import logging

logger = logging.getLogger("OwnerActions")

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/api/system-state")
def get_system_state(db: Session = Depends(get_db)):
    """Decision Intelligence Layer — read-only system state."""
    row = db.query(models.SystemState).first()
    if not row:
        row = models.SystemState(current_mode="DEBATE", severity_score=0)
        db.add(row)
        db.commit()
        db.refresh(row)
    return {
        "current_mode": row.current_mode,
        "severity_score": row.severity_score,
        "last_updated": row.last_updated.isoformat() if row.last_updated else None,
    }

@router.get("/api/inventory")
def get_inventory(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str = Query("", description="Search by SKU or product name"),
    category: str = Query("", description="Filter by category"),
    status: str = Query("", description="Filter by status"),
    db: Session = Depends(get_db),
):
    q = db.query(models.InventoryItem)

    if search:
        term = f"%{search}%"
        q = q.filter(or_(
            models.InventoryItem.sku.ilike(term),
            models.InventoryItem.product_name.ilike(term),
        ))
    if category:
        q = q.filter(models.InventoryItem.category == category)
    if status:
        q = q.filter(models.InventoryItem.status == status)

    total = q.count()
    items = q.order_by(models.InventoryItem.sku).offset((page - 1) * page_size).limit(page_size).all()

    return {
        "items": [
            {
                "id": i.id, "sku": i.sku, "product_name": i.product_name,
                "category": i.category, "brand": i.brand, "supplier": i.supplier,
                "stock_quantity": i.stock_quantity, "reorder_level": i.reorder_level,
                "cost_price": i.cost_price, "selling_price": i.selling_price,
                "warehouse_location": i.warehouse_location,
                "last_updated": i.last_updated.isoformat() if i.last_updated else None,
                "status": i.status,
            }
            for i in items
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }

@router.get("/api/inventory/summary")
def get_inventory_summary(db: Session = Depends(get_db)):
    total = db.query(func.count(models.InventoryItem.id)).scalar() or 0
    low = db.query(func.count(models.InventoryItem.id)).filter(models.InventoryItem.status == "Low Stock").scalar() or 0
    oos = db.query(func.count(models.InventoryItem.id)).filter(models.InventoryItem.status == "Out of Stock").scalar() or 0
    total_value = db.query(func.sum(models.InventoryItem.cost_price * models.InventoryItem.stock_quantity)).scalar() or 0
    return {"total": total, "low_stock": low, "out_of_stock": oos, "total_value": round(total_value, 2)}


@router.post("/api/owner/approve-refill/{event_id}")
def approve_refill(event_id: int, db: Session = Depends(get_db)):
    """
    Owner approves a refill request.
    Sends real email to supplier + SMS/WhatsApp to owner.
    """
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    item_id = event.payload.get("item_id")
    item = db.query(models.InventoryItem).filter(models.InventoryItem.id == item_id).first()
    
    if item:
        # Get vendor email
        vendor = db.query(models.Vendor).filter(models.Vendor.id == item.supplier_id).first()
        vendor_email = vendor.email if vendor else "supplier@example.com"
        
        # 1. Send real email to supplier via Gmail OAuth
        try:
            send_email_to_supplier(vendor_email, item.product_name, item.reorder_quantity)
            logger.info(f"Supplier email sent to {vendor_email} for {item.product_name}")
        except Exception as e:
            logger.error(f"Supplier email failed: {e}")
        
        # 2. Send SMS to owner
        try:
            sms_msg = f"Procure-IQ: Order placed for {item.reorder_quantity}x {item.product_name} to {vendor_email}"
            send_sms_to_owner(sms_msg)
        except Exception as e:
            logger.warning(f"SMS failed (non-fatal): {e}")
        
        # 3. Send WhatsApp to owner
        try:
            wa_msg = (
                f"Procure-IQ Order Confirmed\n\n"
                f"Item: {item.product_name}\n"
                f"Quantity: {item.reorder_quantity} units\n"
                f"Supplier: {vendor_email}\n"
                f"Status: Order Sent"
            )
            send_whatsapp_to_owner(wa_msg)
        except Exception as e:
            logger.warning(f"WhatsApp failed (non-fatal): {e}")
        
        # Update Event
        event.status = "COMPLETED"
        event.processed_at = datetime.datetime.utcnow()
        
        # Update Inventory
        item.last_updated = datetime.datetime.utcnow()
        item.stock_quantity += item.reorder_quantity
        
        db.commit()
        return {"status": "success", "message": f"Order sent to {vendor_email} and inventory updated."}
    
    return {"status": "error", "message": "Item not found"}

@router.get("/api/alerts")
def get_alerts(db: Session = Depends(get_db)):
    return db.query(models.Event).filter(models.Event.event_type == "STOCK_ALERT").all()
