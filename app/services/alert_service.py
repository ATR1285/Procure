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


import uuid
from ..models import AlertLog, PendingApproval

logger = logging.getLogger(__name__)


async def check_low_stock(db: Session) -> List[dict]:
    """
    Check inventory for items below stock threshold.
    """
    from ..models import InventoryItem
    
    low_stock_items = []
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
                "reorder_quantity": getattr(item, 'reorder_quantity', threshold * 5),
                "sku": getattr(item, 'sku', 'N/A'),
                "unit_price": getattr(item, 'unit_price', 0.0)
            })
            
    return low_stock_items


async def send_approval_request(db: Session, item: dict, token: str) -> dict:
    """
    Send approval request via Email and SMS.
    """
    approval_link = f"{settings.BASE_URL}/api/approve/{token}"
    email_sent = False
    sms_sent = False
    
    # 1. Send Email
    if GMAIL_AVAILABLE and settings.GMAIL_CLIENT_ID:
        try:
            creds = Credentials(
                token=None,
                refresh_token=settings.GMAIL_REFRESH_TOKEN,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=settings.GMAIL_CLIENT_ID,
                client_secret=settings.GMAIL_CLIENT_SECRET
            )
            service = build('gmail', 'v1', credentials=creds)
            
            est_cost = item['reorder_quantity'] * item['unit_price']
            
            email_body = f"""
            <html>
            <body>
                <h2 style="color: #d9534f;">🚨 Low Stock Alert: {item['item_name']}</h2>
                <p><strong>Current Stock:</strong> {item['current_stock']} (Threshold: {item['threshold']})</p>
                
                <div style="border: 1px solid #ccc; padding: 15px; border-radius: 5px; background-color: #f9f9f9;">
                    <h3>🤖 AI Reorder Suggestion</h3>
                    <p><strong>Quantity:</strong> {item['reorder_quantity']} units</p>
                    <p><strong>Est. Cost:</strong> ${est_cost:.2f}</p>
                    <p><strong>Reasoning:</strong> Stock level is critical. Recommended reorder quantity based on historical usage.</p>
                </div>
                
                <br>
                <div style="text-align: center;">
                    <a href="{approval_link}" style="background-color: #5cb85c; color: white; padding: 12px 20px; text-decoration: none; border-radius: 4px; font-weight: bold; font-size: 16px;">
                        ✅ REVIEW & APPROVE ORDER
                    </a>
                    <br><br>
                    <a href="{settings.BASE_URL}/api/dismiss/{token}" style="color: #777; font-size: 12px;">Dismiss Alert</a>
                </div>
                
                <p style="font-size: 10px; color: #999; margin-top: 30px;">
                    This serves as a formal purchase requisition request.<br>
                    Token: {token}
                </p>
            </body>
            </html>
            """
            
            message = MIMEText(email_body, 'html')
            message['to'] = settings.OWNER_EMAIL
            message['subject'] = f"ACTION REQUIRED: Approve Reorder for {item['item_name']}"
            
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
            service.users().messages().send(userId='me', body={'raw': raw_message}).execute()
            email_sent = True
            logger.info(f"Approval email sent for {item['item_name']}")
            
        except Exception as e:
            logger.error(f"Failed to send approval email: {e}")

    # 2. Send SMS
    if TWILIO_AVAILABLE and settings.TWILIO_ACCOUNT_SID:
        try:
            client = TwilioClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            sms_body = f"🚨 Low Stock: {item['item_name']} ({item['current_stock']} left). Approve reorder: {approval_link}"
            client.messages.create(body=sms_body, from_=settings.TWILIO_FROM_NUMBER, to=settings.OWNER_PHONE)
            sms_sent = True
            logger.info(f"Approval SMS sent for {item['item_name']}")
        except Exception as e:
            logger.error(f"Failed to send SMS: {e}")

    # 3. Send WhatsApp (Twilio WhatsApp sandbox / approved number)
    if TWILIO_AVAILABLE and settings.TWILIO_ACCOUNT_SID and settings.OWNER_PHONE:
        try:
            client = TwilioClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            est_cost = item['reorder_quantity'] * item['unit_price']
            wa_body = (
                f"📦 *Procure-IQ Low Stock Alert*\n\n"
                f"*Item:* {item['item_name']}\n"
                f"*Current Stock:* {item['current_stock']} units\n"
                f"*Threshold:* {item['threshold']} units\n"
                f"*Est. Reorder Cost:* ${est_cost:,.2f}\n\n"
                f"✅ Approve: {approval_link}"
            )
            client.messages.create(
                body=wa_body,
                from_=f"whatsapp:{settings.TWILIO_FROM_NUMBER}",
                to=f"whatsapp:{settings.OWNER_PHONE}"
            )
            logger.info(f"WhatsApp alert sent for {item['item_name']}")
        except Exception as e:
            logger.warning(f"WhatsApp alert failed (non-critical): {e}")

    return {"email_sent": email_sent, "sms_sent": sms_sent}



async def process_stock_alerts(db: Session) -> dict:
    """
    Check stock and generate approval requests.
    """
    logger.debug("Running stock alert check...")
    
    # 1. Check for low stock items
    low_stock_items = await check_low_stock(db)
    
    if not low_stock_items:
        return {"items_checked": 0, "alerts_generated": 0}
    
    alerts_generated = 0
    results = {"email_sent": False, "sms_sent": False}
    
    for item in low_stock_items:
        # Check for existing active approval request
        existing_approval = db.query(PendingApproval).filter(
            PendingApproval.item_id == item['item_id'],
            PendingApproval.status == 'awaiting_owner'
        ).first()
        
        if existing_approval:
            logger.debug(f"Pending approval already exists for {item['item_name']}")
            continue
            
        # Create new approval request
        token = str(uuid.uuid4())
        est_cost = item['reorder_quantity'] * item['unit_price']
        
        approval = PendingApproval(
            item_id=item['item_id'],
            suggested_quantity=item['reorder_quantity'],
            estimated_cost=est_cost,
            ai_reasoning=f"Stock ({item['current_stock']}) <= Threshold ({item['threshold']})",
            token=token,
            expires_at=datetime.now() + timedelta(hours=48),
            status="awaiting_owner"
        )
        db.add(approval)
        db.commit()
        
        # Send notifications
        res = await send_approval_request(db, item, token)
        results["email_sent"] = res["email_sent"] or results["email_sent"]
        results["sms_sent"] = res["sms_sent"] or results["sms_sent"]
        
        # Log alert
        alert = AlertLog(
            item_id=item['item_id'],
            alert_type="approval_requested",
            message=f"Approval requested for {item['item_name']}",
            email_sent=res["email_sent"],
            sms_sent=res["sms_sent"]
        )
        db.add(alert)
        db.commit()
        
        alerts_generated += 1
        
    return {
        "items_checked": len(low_stock_items),
        "alerts_generated": alerts_generated,
        "email_sent": results["email_sent"],
        "sms_sent": results["sms_sent"]
    }
