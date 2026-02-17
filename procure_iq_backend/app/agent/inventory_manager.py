import logging
import datetime
from sqlalchemy.orm import Session
from .. import models
from ..services.notifications import send_sms_to_owner

logger = logging.getLogger("InventoryAgent")

def check_inventory_levels(db: Session):
    """
    Scans the inventory table for items that are low in stock.
    Triggers 'STOCK_ALERT' events and notifies the owner.
    """
    logger.info("Scanning inventory levels...")
    
    # Corrected logic: check for LOW stock (quantity <= reorder_threshold)
    items_to_refill = db.query(models.InventoryItem).filter(
        models.InventoryItem.quantity <= models.InventoryItem.reorder_threshold
    ).all()
    
    for item in items_to_refill:
        # Check if we already have a pending alert for this item to avoid spam
        existing_event = db.query(models.Event).filter(
            models.Event.event_type == "STOCK_ALERT",
            models.Event.status == "PENDING"
        ).all()
        
        is_already_alerted = any(e.payload.get("item_id") == item.id for e in existing_event)
        
        if not is_already_alerted:
            logger.warning(f"🚨 Low Stock Alert: {item.name} is at {item.quantity} (Threshold: {item.reorder_threshold})")
            
            # Create Event for UI/Audit
            alert_payload = {
                "item_id": item.id,
                "item_name": item.name,
                "current_qty": item.quantity,
                "threshold": item.reorder_threshold,
                "message": f"Low stock detected for {item.name}. Reorder quantity suggested: {item.reorder_quantity}"
            }
            
            new_event = models.Event(
                event_type="STOCK_ALERT",
                payload=alert_payload,
                status="PENDING"
            )
            db.add(new_event)
            
            # Record SMS Log
            sms_msg = f"ProcureIQ Alert: {item.name} is running low ({item.quantity} left). Threshold is {item.reorder_threshold}. Suggest reordering {item.reorder_quantity} units."
            send_sms_to_owner(sms_msg)
            
            # Create AlertLog with correct fields
            alert_log = models.AlertLog(
                item_id=item.id,
                alert_type="low_stock",
                message=sms_msg,
                sms_sent=True,
                email_sent=False # Emails sent via owner_actions after approval
            )
            db.add(alert_log)
            db.commit()
            
    return len(items_to_refill)
