import logging
import datetime
from sqlalchemy.orm import Session
from .. import models
from ..services.notifications import send_sms_to_owner

logger = logging.getLogger("InventoryAgent")

def check_inventory_levels(db: Session):
    """
    Scans the inventory table for items that have exceeded their threshold.
    Triggers 'STOCK_ALERT' events and notifies the owner.
    """
    logger.info("Scanning inventory levels...")
    
    items_to_refill = db.query(models.Inventory).filter(
        models.Inventory.quantity > models.Inventory.limit_threshold
    ).all()
    
    for item in items_to_refill:
        # Check if we already have a pending alert for this item to avoid spam
        existing_event = db.query(models.Event).filter(
            models.Event.event_type == "STOCK_ALERT",
            models.Event.payload["item_id"].as_integer() == item.id,
            models.Event.status == "PENDING"
        ).first()
        
        if not existing_event:
            logger.warning(f"🚨 Inventory Alert: {item.item_name} is at {item.quantity} (Limit: {item.limit_threshold})")
            
            # Create Event for UI/Audit
            alert_payload = {
                "item_id": item.id,
                "item_name": item.item_name,
                "current_qty": item.quantity,
                "threshold": item.limit_threshold,
                "message": f"Excessive stock detected for {item.item_name}. Should we pause incoming orders or replenish differently?"
            }
            
            new_event = models.Event(
                event_type="STOCK_ALERT",
                payload=alert_payload,
                status="PENDING"
            )
            db.add(new_event)
            
            # Record SMS Log
            sms_msg = f"ProcureIQ Alert: {item.item_name} quantity ({item.quantity}) exceeded limit of {item.limit_threshold}. Please check dashboard to approve replenishment plan."
            send_sms_to_owner(sms_msg)
            
            sms_log = models.SMSLog(
                recipient_number="+91 9876543210",
                message_body=sms_msg,
                related_item_id=item.id
            )
            db.add(sms_log)
            db.commit()
            
    return len(items_to_refill)
