"""
Owner Approval Flow - Token-based approval system

Provides secure, time-limited approval links for invoice approval/rejection.
Tokens are sent via email and SMS, allowing owners to approve invoices
with a single click.

Features:
- Secure token generation (32-byte random)
- Configurable expiry (default: 48 hours)
- One-time use tokens
- Email + SMS delivery
- Audit trail (IP, user agent, timestamp)
- Automatic status updates

Usage:
    # Generate approval request
    POST /api/approval/request
    {
        "invoice_id": 123,
        "threshold_exceeded": true
    }
    
    # Approve/Reject via token
    GET /api/approval/{token}/approve
    GET /api/approval/{token}/reject
"""

import secrets
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel

# Add parent directory to path for imports
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config import settings
from app.database import SessionLocal
from app import models

router = APIRouter()


# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class ApprovalRequest(BaseModel):
    """Request body for creating approval request"""
    invoice_id: int
    threshold_exceeded: bool = False
    reason: Optional[str] = None


class ApprovalResponse(BaseModel):
    """Response for approval request creation"""
    success: bool
    message: str
    approve_url: Optional[str] = None
    reject_url: Optional[str] = None
    email_sent: bool = False
    sms_sent: bool = False


def generate_approval_token() -> str:
    """Generate a secure random token for approval links."""
    return secrets.token_urlsafe(32)


async def send_approval_email(invoice: models.Invoice, approve_url: str, reject_url: str) -> bool:
    """
    Send approval request email via Gmail OAuth.
    
    Args:
        invoice: Invoice requiring approval
        approve_url: Full URL for approval
        reject_url: Full URL for rejection
    
    Returns:
        True if email sent successfully
    """
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from email.mime.text import MIMEText
        import base64
        
        if not settings.GMAIL_CLIENT_ID or not settings.GMAIL_CLIENT_SECRET:
            print("[WARN] Gmail OAuth not configured - skipping email")
            return False
        
        # Build credentials
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
        email_body = f"""
Invoice Approval Required - Procure-IQ

Invoice Details:
- Invoice Number: {invoice.invoice_number}
- Amount: ${invoice.total_amount:.2f} {invoice.currency}
- Vendor: {invoice.vendor_id or 'Unknown'}
- Date: {invoice.invoice_date.strftime('%Y-%m-%d')}
- Confidence Score: {invoice.confidence_score or 'N/A'}%

Reason for Approval:
{invoice.reasoning_note or 'Amount exceeds automatic approval threshold'}

Actions:
To APPROVE this invoice, click here:
{approve_url}

To REJECT this invoice, click here:
{reject_url}

This link expires in {settings.APPROVAL_TOKEN_EXPIRY_HOURS} hours.

---
Procure-IQ Autonomous Procurement System
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        # Create message
        message = MIMEText(email_body)
        message['to'] = settings.OWNER_EMAIL
        message['subject'] = f"[Procure-IQ] Approval Required - Invoice {invoice.invoice_number}"
        
        # Encode and send
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        send_message = service.users().messages().send(
            userId='me',
            body={'raw': raw_message}
        ).execute()
        
        print(f"[OK] Approval email sent: {send_message['id']}")
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to send approval email: {e}")
        return False


async def send_approval_sms(invoice: models.Invoice, approve_url: str, reject_url: str) -> bool:
    """
    Send approval request SMS via Twilio.
    
    Args:
        invoice: Invoice requiring approval
        approve_url: Full URL for approval
        reject_url: Full URL for rejection
    
    Returns:
        True if SMS sent successfully
    """
    try:
        from twilio.rest import Client as TwilioClient
        
        if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
            print("[WARN] Twilio not configured - skipping SMS")
            return False
        
        if not settings.OWNER_PHONE:
            print("[WARN] Owner phone not configured - skipping SMS")
            return False
        
        # Initialize Twilio client
        client = TwilioClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        
        # Build SMS body (keep under 160 characters for standard SMS)
        sms_body = f"Procure-IQ: Invoice {invoice.invoice_number} (${invoice.total_amount:.2f}) needs approval. Check email for details."
        
        # Send SMS
        message = client.messages.create(
            body=sms_body,
            from_=settings.TWILIO_FROM_NUMBER,
            to=settings.OWNER_PHONE
        )
        
        print(f"[OK] Approval SMS sent: {message.sid}")
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to send approval SMS: {e}")
        return False


@router.post("/request", response_model=ApprovalResponse)
async def request_approval(
    request: ApprovalRequest,
    db: Session = Depends(get_db)
):
    """
    Create approval request for an invoice.
    
    Generates secure tokens, sends email/SMS, and returns approval URLs.
    
    Args:
        request: Approval request with invoice_id
        db: Database session
    
    Returns:
        ApprovalResponse with URLs and delivery status
    """
    # 1. Fetch invoice
    invoice = db.query(models.Invoice).filter(models.Invoice.id == request.invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # 2. Check if already approved/rejected
    if invoice.status in ["APPROVED", "REJECTED"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invoice already {invoice.status.lower()}"
        )
    
    # 3. Generate approval tokens
    approve_token = generate_approval_token()
    reject_token = generate_approval_token()
    
    expiry_time = datetime.now() + timedelta(hours=settings.APPROVAL_TOKEN_EXPIRY_HOURS)
    
    # 4. Create token records
    approve_token_record = models.ApprovalToken(
        token=approve_token,
        invoice_id=invoice.id,
        action_type="approve",
        expires_at=expiry_time
    )
    
    reject_token_record = models.ApprovalToken(
        token=reject_token,
        invoice_id=invoice.id,
        action_type="reject",
        expires_at=expiry_time
    )
    
    db.add(approve_token_record)
    db.add(reject_token_record)
    db.commit()
    
    # 5. Build approval URLs
    base_url = settings.BASE_URL
    approve_url = f"{base_url}/api/approval/{approve_token}/approve"
    reject_url = f"{base_url}/api/approval/{reject_token}/reject"
    
    # 6. Send email and SMS
    email_sent = await send_approval_email(invoice, approve_url, reject_url)
    sms_sent = await send_approval_sms(invoice, approve_url, reject_url)
    
    # 7. Update invoice audit trail
    invoice.audit_trail.append({
        "t": "approval_requested",
        "m": f"Approval request sent (email={email_sent}, sms={sms_sent})",
        "timestamp": datetime.now().isoformat()
    })
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(invoice, "audit_trail")
    db.commit()
    
    return ApprovalResponse(
        success=True,
        message="Approval request created successfully",
        approve_url=approve_url,
        reject_url=reject_url,
        email_sent=email_sent,
        sms_sent=sms_sent
    )


@router.get("/{token}/approve")
async def approve_invoice(
    token: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Approve invoice via token link.
    
    Args:
        token: Approval token from email/SMS
        request: FastAPI request (for IP/user agent)
        db: Database session
    
    Returns:
        HTML page with approval confirmation
    """
    # 1. Fetch token
    token_record = db.query(models.ApprovalToken).filter(
        models.ApprovalToken.token == token,
        models.ApprovalToken.action_type == "approve"
    ).first()
    
    if not token_record:
        raise HTTPException(status_code=404, detail="Invalid approval token")
    
    # 2. Check if already used
    if token_record.is_used:
        raise HTTPException(status_code=400, detail="Token already used")
    
    # 3. Check if expired
    if datetime.now() > token_record.expires_at:
        raise HTTPException(status_code=400, detail="Token expired")
    
    # 4. Fetch invoice
    invoice = db.query(models.Invoice).filter(models.Invoice.id == token_record.invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # 5. Update invoice status
    invoice.status = "APPROVED"
    invoice.audit_trail.append({
        "t": "owner_approved",
        "m": f"Approved by owner via token",
        "ip": request.client.host,
        "timestamp": datetime.now().isoformat()
    })
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(invoice, "audit_trail")
    
    # 6. Mark token as used
    token_record.is_used = True
    token_record.used_at = datetime.now()
    token_record.ip_address = request.client.host
    token_record.user_agent = request.headers.get("user-agent", "Unknown")
    
    db.commit()
    
    # 7. Return HTML confirmation
    return {
        "success": True,
        "message": f"Invoice {invoice.invoice_number} approved successfully",
        "invoice_id": invoice.id,
        "amount": invoice.total_amount,
        "status": invoice.status
    }


@router.get("/{token}/reject")
async def reject_invoice(
    token: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Reject invoice via token link.
    
    Args:
        token: Rejection token from email/SMS
        request: FastAPI request (for IP/user agent)
        db: Database session
    
    Returns:
        HTML page with rejection confirmation
    """
    # 1. Fetch token
    token_record = db.query(models.ApprovalToken).filter(
        models.ApprovalToken.token == token,
        models.ApprovalToken.action_type == "reject"
    ).first()
    
    if not token_record:
        raise HTTPException(status_code=404, detail="Invalid rejection token")
    
    # 2. Check if already used
    if token_record.is_used:
        raise HTTPException(status_code=400, detail="Token already used")
    
    # 3. Check if expired
    if datetime.now() > token_record.expires_at:
        raise HTTPException(status_code=400, detail="Token expired")
    
    # 4. Fetch invoice
    invoice = db.query(models.Invoice).filter(models.Invoice.id == token_record.invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # 5. Update invoice status
    invoice.status = "REJECTED"
    invoice.audit_trail.append({
        "t": "owner_rejected",
        "m": f"Rejected by owner via token",
        "ip": request.client.host,
        "timestamp": datetime.now().isoformat()
    })
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(invoice, "audit_trail")
    
    # 6. Mark token as used
    token_record.is_used = True
    token_record.used_at = datetime.now()
    token_record.ip_address = request.client.host
    token_record.user_agent = request.headers.get("user-agent", "Unknown")
    
    db.commit()
    
    # 7. Return HTML confirmation
    return {
        "success": True,
        "message": f"Invoice {invoice.invoice_number} rejected successfully",
        "invoice_id": invoice.id,
        "amount": invoice.total_amount,
        "status": invoice.status
    }


@router.get("/{token}/status")
async def check_token_status(
    token: str,
    db: Session = Depends(get_db)
):
    """
    Check status of an approval token.
    
    Args:
        token: Approval/rejection token
        db: Database session
    
    Returns:
        Token status information
    """
    token_record = db.query(models.ApprovalToken).filter(
        models.ApprovalToken.token == token
    ).first()
    
    if not token_record:
        raise HTTPException(status_code=404, detail="Token not found")
    
    return {
        "token": token,
        "action_type": token_record.action_type,
        "is_used": token_record.is_used,
        "is_expired": datetime.now() > token_record.expires_at,
        "created_at": token_record.created_at.isoformat(),
        "expires_at": token_record.expires_at.isoformat(),
        "used_at": token_record.used_at.isoformat() if token_record.used_at else None
    }
