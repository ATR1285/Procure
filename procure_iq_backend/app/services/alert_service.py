"""
Low Stock Alert Service

Monitors inventory levels and sends automated alerts via email (Gmail OAuth) 
and SMS (Twilio) when stock falls below configured thresholds.

Features:
- Automatic inventory monitoring
- Email alerts via Gmail OAuth2
- SMS alerts via Twilio
- Alert deduplication (prevents spam)
- Configurable thresholds per item
- Alert history tracking

Usage:
    from app.services.alert_service import process_stock_alerts
    
    # Run in agent loop
    await process_stock_alerts(db)
"""

import logging
from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

# Add parent directory to path for config import
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config import settings

# Conditional imports
try:
    from twilio.rest import Client as TwilioClient
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False
    logging.warning("twilio not installed - SMS alerts unavailable")

try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from email.mime.text import MIMEText
    import base64
    GMAIL_AVAILABLE = True
except ImportError:
    GMAIL_AVAILABLE = False
    logging.warning("google-api-python-client not installed - Email alerts unavailable")


logger = logging.getLogger(__name__)


async def check_low_stock(db: Session) -> List[dict]:
    """
    Check inventory for items below stock threshold.
    
    Args:
        db: Database session
    
    Returns:
        List of items with low stock:
        [
            {
                "item_id": 1,
                "item_name": "Widget A",
                "current_stock": 5,
                "threshold": 10,
                "reorder_quantity": 50
            },
            ...
        ]
    """
    from ..models import InventoryItem
    
    low_stock_items = []
    
    # Query all inventory items
    items = db.query(InventoryItem).all()
    
    for item in items:
        threshold = getattr(item, 'reorder_threshold', settings.STOCK_ALERT_THRESHOLD)
        current_stock = getattr(item, 'quantity', 0)
        
        if current_stock <= threshold:
            low_stock_items.append({
                "item_id": item.id,
                "item_name": item.name,
                "current_stock": current_stock,
                "threshold": threshold,
                "reorder_quantity": getattr(item, 'reorder_quantity', threshold * 5)
            })
            
            logger.info(f"Low stock detected: {item.name} ({current_stock} <= {threshold})")
    
    return low_stock_items


async def send_stock_alert_email(items: List[dict]) -> bool:
    """
    Send low stock alert email via Gmail OAuth.
    
    Args:
        items: List of low stock items from check_low_stock()
    
    Returns:
        True if email sent successfully, False otherwise
    """
    if not GMAIL_AVAILABLE:
        logger.warning("Gmail API not available - skipping email alert")
        return False
    
    if not settings.GMAIL_CLIENT_ID or not settings.GMAIL_CLIENT_SECRET:
        logger.warning("Gmail OAuth not configured - skipping email alert")
        return False
    
    try:
        # Build credentials from settings
        creds = Credentials(
            token=None,
            refresh_token=settings.GMAIL_REFRESH_TOKEN,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.GMAIL_CLIENT_ID,
            client_secret=settings.GMAIL_CLIENT_SECRET
        )
        
        # Build Gmail service
        service = build('gmail', 'v1', credentials=creds)
        
        # Build email body
        item_list = "\n".join([
            f"- {item['item_name']}: {item['current_stock']} units (threshold: {item['threshold']})"
            for item in items
        ])
        
        email_body = f"""
Low Stock Alert - Procure-IQ

The following items are below their reorder thresholds:

{item_list}

Recommended Actions:
{chr(10).join([f"- Reorder {item['reorder_quantity']} units of {item['item_name']}" for item in items])}

This is an automated alert from Procure-IQ.
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        # Create message
        message = MIMEText(email_body)
        message['to'] = settings.OWNER_EMAIL
        message['subject'] = f"[Procure-IQ] Low Stock Alert - {len(items)} item(s)"
        
        # Encode message
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        
        # Send email
        send_message = service.users().messages().send(
            userId='me',
            body={'raw': raw_message}
        ).execute()
        
        logger.info(f"Email alert sent successfully: {send_message['id']}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email alert: {e}")
        return False


async def send_stock_alert_sms(items: List[dict]) -> bool:
    """
    Send low stock alert SMS via Twilio.
    
    Args:
        items: List of low stock items from check_low_stock()
    
    Returns:
        True if SMS sent successfully, False otherwise
    """
    if not TWILIO_AVAILABLE:
        logger.warning("Twilio not available - skipping SMS alert")
        return False
    
    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
        logger.warning("Twilio not configured - skipping SMS alert")
        return False
    
    if not settings.OWNER_PHONE:
        logger.warning("Owner phone not configured - skipping SMS alert")
        return False
    
    try:
        # Initialize Twilio client
        client = TwilioClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        
        # Build SMS body (max 160 characters for standard SMS)
        if len(items) == 1:
            sms_body = f"Procure-IQ Alert: {items[0]['item_name']} low stock ({items[0]['current_stock']} units)"
        else:
            sms_body = f"Procure-IQ Alert: {len(items)} items low stock. Check email for details."
        
        # Send SMS
        message = client.messages.create(
            body=sms_body,
            from_=settings.TWILIO_FROM_NUMBER,
            to=settings.OWNER_PHONE
        )
        
        logger.info(f"SMS alert sent successfully: {message.sid}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send SMS alert: {e}")
        return False


async def process_stock_alerts(db: Session) -> dict:
    """
    Main orchestrator for stock alert processing.
    
    This function should be called periodically (e.g., every 60 seconds)
    by the agent loop.
    
    Workflow:
    1. Check inventory for low stock items
    2. Filter out recently alerted items (prevent spam)
    3. Send email alert if items found
    4. Send SMS alert if items found
    5. Record alerts in database
    
    Args:
        db: Database session
    
    Returns:
        Dict with alert results:
        {
            "items_checked": 50,
            "low_stock_items": 3,
            "email_sent": True,
            "sms_sent": True,
            "alerts_recorded": 3
        }
    """
    from ..models import AlertLog
    
    logger.debug("Running stock alert check...")
    
    # 1. Check for low stock items
    low_stock_items = await check_low_stock(db)
    
    if not low_stock_items:
        logger.debug("No low stock items found")
        return {
            "items_checked": db.query(db.query(db.query).count()),
            "low_stock_items": 0,
            "email_sent": False,
            "sms_sent": False,
            "alerts_recorded": 0
        }
    
    # 2. Filter out recently alerted items (within last 24 hours)
    cutoff_time = datetime.now() - timedelta(hours=24)
    items_to_alert = []
    
    for item in low_stock_items:
        # Check if alert was sent recently
        recent_alert = db.query(AlertLog).filter(
            AlertLog.item_id == item['item_id'],
            AlertLog.alert_type == 'low_stock',
            AlertLog.created_at > cutoff_time
        ).first()
        
        if not recent_alert:
            items_to_alert.append(item)
    
    if not items_to_alert:
        logger.info(f"Found {len(low_stock_items)} low stock items, but all were alerted recently")
        return {
            "items_checked": len(low_stock_items),
            "low_stock_items": len(low_stock_items),
            "email_sent": False,
            "sms_sent": False,
            "alerts_recorded": 0,
            "reason": "All items alerted within last 24 hours"
        }
    
    logger.info(f"Sending alerts for {len(items_to_alert)} items")
    
    # 3. Send email alert
    email_sent = await send_stock_alert_email(items_to_alert)
    
    # 4. Send SMS alert
    sms_sent = await send_stock_alert_sms(items_to_alert)
    
    # 5. Record alerts in database
    alerts_recorded = 0
    for item in items_to_alert:
        alert_log = AlertLog(
            item_id=item['item_id'],
            alert_type='low_stock',
            message=f"Low stock: {item['item_name']} ({item['current_stock']} units)",
            email_sent=email_sent,
            sms_sent=sms_sent,
            created_at=datetime.now()
        )
        db.add(alert_log)
        alerts_recorded += 1
    
    db.commit()
    
    logger.info(f"Stock alerts processed: {alerts_recorded} alerts recorded")
    
    return {
        "items_checked": len(low_stock_items),
        "low_stock_items": len(items_to_alert),
        "email_sent": email_sent,
        "sms_sent": sms_sent,
        "alerts_recorded": alerts_recorded
    }
