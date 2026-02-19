from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import logging
from ..database import get_db
from ..models import PendingApproval, PurchaseOrder, InventoryItem, Vendor
from ..services.email_service import EmailIngestionService # For helper methods if needed, or just use build()
from config import settings
# Imports for email sending
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from email.mime.text import MIMEText
import base64

router = APIRouter()
logger = logging.getLogger(__name__)

def get_gmail_service():
    """Helper to get Gmail service."""
    if not settings.GMAIL_CLIENT_ID or not settings.GMAIL_CLIENT_SECRET:
        return None
    try:
        creds = Credentials(
            token=None,
            refresh_token=settings.GMAIL_REFRESH_TOKEN,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.GMAIL_CLIENT_ID,
            client_secret=settings.GMAIL_CLIENT_SECRET
        )
        return build('gmail', 'v1', credentials=creds)
    except Exception as e:
        logger.error(f"Failed to create Gmail service: {e}")
        return None

def send_email(to_email: str, subject: str, html_content: str):
    """Helper to send HTML email."""
    service = get_gmail_service()
    if not service:
        logger.warning("Gmail service unavailable, skipping email.")
        return False
    
    try:
        message = MIMEText(html_content, 'html')
        message['to'] = to_email
        message['subject'] = subject
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        service.users().messages().send(userId='me', body={'raw': raw_message}).execute()
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False

@router.get("/approve/{token}", response_class=HTMLResponse)
async def get_approval_form(token: str, db: Session = Depends(get_db)):
    """
    Render the owner approval form.
    """
    approval = db.query(PendingApproval).filter(PendingApproval.token == token).first()
    
    if not approval:
        return HTMLResponse(content="<h1>Invalid or Expired Token</h1><p>This link is no longer valid.</p>", status_code=404)
        
    if approval.status != "awaiting_owner":
        return HTMLResponse(content=f"<h1>Request Already Processed</h1><p>Status: {approval.status}</p>", status_code=200)
    
    if approval.expires_at < datetime.utcnow():
        approval.status = "expired"
        db.commit()
        return HTMLResponse(content="<h1>Link Expired</h1><p>This approval request has expired.</p>", status_code=400)
    
    # Fetch item details
    item = db.query(InventoryItem).filter(InventoryItem.id == approval.item_id).first()
    if not item:
        return HTMLResponse(content="<h1>Item Not Found</h1>", status_code=404)
        
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Approve Order - Procure-IQ</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f4f9; padding: 20px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            h1 {{ color: #333; }}
            .item-card {{ background: #f8f9fa; padding: 15px; border-left: 4px solid #007bff; margin-bottom: 20px; }}
            .details {{ margin-bottom: 20px; }}
            label {{ display: block; margin-top: 10px; font-weight: bold; }}
            input[type="number"] {{ width: 100%; padding: 10px; margin-top: 5px; font-size: 16px; border: 1px solid #ddd; border-radius: 4px; }}
            .cost-display {{ font-size: 1.2em; color: #28a745; font-weight: bold; margin-top: 10px; }}
            .buttons {{ margin-top: 30px; display: flex; gap: 10px; }}
            button {{ flex: 1; padding: 12px; border: none; border-radius: 4px; font-size: 16px; cursor: pointer; }}
            .btn-confirm {{ background-color: #28a745; color: white; }}
            .btn-cancel {{ background-color: #6c757d; color: white; }}
        </style>
        <script>
            function updateCost() {{
                const qty = document.getElementById('quantity').value;
                const price = {item.unit_price};
                const total = (qty * price).toFixed(2);
                document.getElementById('total_cost').innerText = '$' + total;
            }}
            
            async def submitOrder() {{
                const qty = document.getElementById('quantity').value;
                const token = "{token}";
                
                if (qty <= 0) {{ alert("Quantity must be greater than 0"); return; }}
                
                const btn = document.querySelector('.btn-confirm');
                btn.disabled = true;
                btn.innerText = "Processing...";
                
                try {{
                    const response = await fetch(`/api/approve/${{token}}/confirm`, {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{ quantity: parseInt(qty) }})
                    }});
                    
                    const result = await response.json();
                    if (result.success) {{
                        document.body.innerHTML = `<div class='container'><h1>✅ Order Confirmed</h1><p>${{result.message}}</p><p>PO Number: <strong>${{result.po_number}}</strong></p></div>`;
                    }} else {{
                        alert("Error: " + result.detail);
                        btn.disabled = false;
                        btn.innerText = "Confirm Order";
                    }}
                }} catch (e) {{
                    alert("Network error");
                    btn.disabled = false;
                    btn.innerText = "Confirm Order";
                }}
            }}
        </script>
    </head>
    <body>
        <div class="container">
            <h1>Approve Purchase Order</h1>
            <div class="item-card">
                <h3>{item.name}</h3>
                <p>Current Stock: <strong>{item.quantity}</strong> (Threshold: {item.reorder_threshold})</p>
                <p>Unit Price: ${item.unit_price:.2f}</p>
            </div>
            
            <div class="details">
                <label for="quantity">Order Quantity (AI Suggested: {approval.suggested_quantity})</label>
                <input type="number" id="quantity" value="{approval.suggested_quantity}" min="1" oninput="updateCost()">
                
                <div class="cost-display">
                    Total: <span id="total_cost">${approval.estimated_cost:.2f}</span>
                </div>
            </div>
            
            <div class="buttons">
                <button class="btn-confirm" onclick="submitOrder()">Confirm Order</button>
                <button class="btn-cancel" onclick="window.location.href='/api/dismiss/{token}'">Dismiss</button>
            </div>
            
            <p style="margin-top: 20px; font-size: 12px; color: #888;">AI Reasoning: {approval.ai_reasoning}</p>
        </div>
    </body>
    </html>
    """
    return html_content

@router.post("/api/approve/{token}/confirm")
async def confirm_approval(token: str, request: Request, db: Session = Depends(get_db)):
    """
    Handle order confirmation.
    """
    data = await request.json()
    quantity = data.get('quantity')
    
    approval = db.query(PendingApproval).filter(PendingApproval.token == token).first()
    
    if not approval or approval.status != "awaiting_owner":
        return JSONResponse({"success": False, "detail": "Invalid or expired token"}, status_code=400)
        
    if not quantity or quantity <= 0:
        return JSONResponse({"success": False, "detail": "Invalid quantity"}, status_code=400)
    
    # 1. Create Purchase Order
    item = db.query(InventoryItem).filter(InventoryItem.id == approval.item_id).first()
    
    # Generate PO Number
    po_number = f"PO-{datetime.now().strftime('%Y%m%d')}-{approval.id:04d}"
    
    total_amount = quantity * item.unit_price
    
    po = PurchaseOrder(
        po_number=po_number,
        item_id=item.id,
        vendor_id=item.supplier_id, 
        quantity=quantity,
        unit_price=item.unit_price,
        total_amount=total_amount,
        status="confirmed_by_owner",
        approved_by_owner=True,
        owner_approved_at=datetime.utcnow(),
        owner_approved_quantity=quantity,
        expected_delivery_date=datetime.utcnow() + timedelta(days=3)
    )
    db.add(po)
    
    # 2. Update Approval Token
    approval.status = "confirmed"
    approval.approved_at = datetime.utcnow()
    approval.approved_quantity = quantity
    
    # 3. Update Inventory Status (Optional, maybe mark as reordered)
    # item.status = "order_placed" # If you had a status field on InventoryItem
    
    db.commit()
    
    # 4. Send Supplier Email
    vendor = db.query(Vendor).filter(Vendor.id == item.supplier_id).first()
    supplier_email = vendor.email if vendor and vendor.email else settings.SUPPLIER_EMAIL
    
    supplier_body = f"""
    <html><body>
    <h2>Purchase Order #{po.po_number}</h2>
    <p>Dear Supplier,</p>
    <p>Please accept this purchase order for the following items:</p>
    <table border="1" cellpadding="5" cellspacing="0">
        <tr><th>Item</th><th>SKU</th><th>Qty</th><th>Unit Price</th><th>Total</th></tr>
        <tr>
            <td>{item.name}</td>
            <td>{item.sku}</td>
            <td>{quantity}</td>
            <td>${item.unit_price:.2f}</td>
            <td>${total_amount:.2f}</td>
        </tr>
    </table>
    <br>
    <p><strong>Total Amount: ${total_amount:.2f}</strong></p>
    <p>Please deliver to:</p>
    <address>
        Procure-IQ Operations<br>
        123 Innovation Drive<br>
        Tech City, TC 94043
    </address>
    <p>Requested Delivery: {po.expected_delivery_date.strftime('%Y-%m-%d')}</p>
    <br>
    <p>Thank you,<br>Procure-IQ Procurement Team</p>
    </body></html>
    """
    send_email(supplier_email, f"Purchase Order {po.po_number}", supplier_body)
    
    # 5. Send Owner Confirmation
    owner_body = f"""
    <html><body>
    <h2>Order Confirmed</h2>
    <p>You have successfully placed an order for <strong>{quantity}x {item.name}</strong>.</p>
    <p>PO Number: {po.po_number}</p>
    <p>Sent to: {supplier_email}</p>
    </body></html>
    """
    send_email(settings.OWNER_EMAIL, f"Order Confirmed: {item.name}", owner_body)
    
    po.email_sent_at = datetime.utcnow()
    db.commit()
    
    return {"success": True, "po_number": po_number, "message": f"Purchase Order {po_number} sent to supplier."}

@router.get("/api/dismiss/{token}", response_class=HTMLResponse)
async def dismiss_approval(token: str, db: Session = Depends(get_db)):
    """
    Dismiss the alert.
    """
    approval = db.query(PendingApproval).filter(PendingApproval.token == token).first()
    if approval and approval.status == "awaiting_owner":
        approval.status = "dismissed"
        approval.dismissed_at = datetime.utcnow()
        db.commit()
        return HTMLResponse("<h1>Alert Dismissed</h1><p>No order was placed.</p>")
    return HTMLResponse("<h1>Invalid Request</h1>", status_code=400)
