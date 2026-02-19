from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, JSON, Text
from sqlalchemy.ext.declarative import declarative_base
import datetime

# IMPORTANT: engine and SessionLocal are defined ONLY in database.py
# This file defines models only. No duplicate DB connections.
Base = declarative_base()

class Vendor(Base):
    __tablename__ = "vendors"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    email = Column(String)
    active = Column(Boolean, default=True)

class VendorAlias(Base):
    __tablename__ = "vendor_aliases"
    id = Column(Integer, primary_key=True, index=True)
    alias_name = Column(String, unique=True, index=True)
    vendor_id = Column(Integer, ForeignKey("vendors.id"))
    confidence = Column(Integer, default=100)
    learned_from_invoice_id = Column(Integer, index=True)

class Invoice(Base):
    __tablename__ = "invoices"
    id = Column(Integer, primary_key=True, index=True)
    invoice_number = Column(String, index=True)
    vendor_id = Column(Integer, ForeignKey("vendors.id"), nullable=True)
    total_amount = Column(Float)
    currency = Column(String, default="USD")
    invoice_date = Column(DateTime, default=datetime.datetime.utcnow)
    status = Column(String, default="PENDING")  # PENDING, PROCESSING, APPROVED, REJECTED, ESCALATED
    extracted_data = Column(JSON, default={})
    confidence_score = Column(Integer, nullable=True)
    reasoning_note = Column(Text, nullable=True)
    is_suspicious = Column(Boolean, default=False)
    audit_trail = Column(JSON, default=[]) # List of events related to this invoice

class ApprovalToken(Base):
    """
    Secure tokens for owner approval via email/SMS links.
    
    Tokens expire after configured hours (default: 48) and can only
    be used once. Provides audit trail for all approval decisions.
    """
    __tablename__ = "approval_tokens"
    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, index=True)  # Secure random token
    invoice_id = Column(Integer, ForeignKey("invoices.id"))
    action_type = Column(String)  # 'approve' or 'reject'
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    expires_at = Column(DateTime)  # Token expiry time
    used_at = Column(DateTime, nullable=True)  # When token was used
    is_used = Column(Boolean, default=False)
    ip_address = Column(String, nullable=True)  # IP of approver
    user_agent = Column(String, nullable=True)  # Browser info


class ConversationMessage(Base):
    """
    Conversation history for memory system.
    
    Stores all conversation messages for multi-turn reasoning and context retention.
    """
    __tablename__ = "conversation_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True, nullable=False)  # Conversation session
    role = Column(String, nullable=False)  # 'user', 'assistant', 'system'
    content = Column(Text, nullable=False)  # Message content
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    message_metadata = Column(JSON, default={})  # Tool calls, costs, model used, etc.


class SystemStatus(Base):
    """
    Tracks health of background services and worker heartbeats.
    """
    __tablename__ = "system_status"
    id = Column(Integer, primary_key=True, index=True)
    service_name = Column(String, unique=True, index=True) # e.g., 'worker', 'api'
    status = Column(String) # 'healthy', 'degraded', 'offline'
    last_heartbeat = Column(DateTime, default=datetime.datetime.utcnow)
    version = Column(String, nullable=True)
    uptime_seconds = Column(Float, default=0.0)


class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String, index=True) # INVOICE_RECEIVED, VENDOR_LEARNED, STOCK_CHECK, SMS_APPROVED
    payload = Column(JSON)
    status = Column(String, default="PENDING") # PENDING, PROCESSING, COMPLETED, FAILED
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)

class InventoryItem(Base):
    """
    Inventory items with stock tracking and reorder management.
    
    Renamed from 'Inventory' for clarity and added reorder fields
    for automated stock alert system.
    """
    __tablename__ = "inventory"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)  # Renamed from item_name for consistency
    brand = Column(String, nullable=True) # Added for v2.0 premium display
    quantity = Column(Integer, default=0)
    reorder_threshold = Column(Integer, default=10)  # Renamed from limit_threshold
    reorder_quantity = Column(Integer, default=50)  # How many to reorder
    supplier_id = Column(Integer, ForeignKey("vendors.id"))
    last_checked = Column(DateTime, default=datetime.datetime.utcnow)
    unit_price = Column(Float, default=0.0)  # For cost tracking
    sku = Column(String, nullable=True)  # Stock Keeping Unit

class AlertLog(Base):
    """
    Alert history for tracking sent notifications.
    
    Prevents duplicate alerts and provides audit trail for
    all email and SMS notifications sent by the system.
    """
    __tablename__ = "alert_logs"
    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("inventory.id"), nullable=True)
    alert_type = Column(String, index=True)  # low_stock, critical_stock, etc.
    message = Column(Text)
    email_sent = Column(Boolean, default=False)
    sms_sent = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    alert_metadata = Column(JSON, default={})  # Additional alert data (renamed from metadata)

class SMSLog(Base):
    __tablename__ = "sms_logs"
    id = Column(Integer, primary_key=True, index=True)
    recipient_number = Column(String)
    message_body = Column(Text)
    status = Column(String, default="SENT")
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    related_item_id = Column(Integer, ForeignKey("inventory.id"), nullable=True)

class PendingApproval(Base):
    """
    Pending approval requests for low stock reordering.
    Requires owner confirmation via secure token before creating a PO.
    """
    __tablename__ = "pending_approvals"
    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("inventory.id"))
    suggested_quantity = Column(Integer)
    estimated_cost = Column(Float)
    ai_reasoning = Column(Text)
    token = Column(String, unique=True, index=True)  # UUID token
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    expires_at = Column(DateTime)
    
    # Status tracking
    status = Column(String, default="awaiting_owner")  # awaiting_owner, confirmed, dismissed, expired
    approved_at = Column(DateTime, nullable=True)
    approved_quantity = Column(Integer, nullable=True)
    dismissed_at = Column(DateTime, nullable=True)

class PurchaseOrder(Base):
    """
    Confirmed Purchase Orders sent to suppliers.
    """
    __tablename__ = "purchase_orders"
    id = Column(Integer, primary_key=True, index=True)
    po_number = Column(String, unique=True, index=True)
    
    item_id = Column(Integer, ForeignKey("inventory.id"))
    vendor_id = Column(Integer, ForeignKey("vendors.id"))
    
    quantity = Column(Integer)
    unit_price = Column(Float)
    total_amount = Column(Float)
    
    status = Column(String, default="confirmed_by_owner")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Owner confirmation details
    approved_by_owner = Column(Boolean, default=True)
    owner_approved_at = Column(DateTime, nullable=True)
    owner_approved_quantity = Column(Integer, nullable=True)
    
    # Supplier communication
    email_sent_at = Column(DateTime, nullable=True)
    expected_delivery_date = Column(DateTime, nullable=True)

class GoodsReceipt(Base):
    """
    Goods receipts for three-way match verification.
    Links received goods to purchase orders for invoice validation.
    """
    __tablename__ = "goods_receipts"
    id = Column(Integer, primary_key=True, index=True)
    purchase_order_id = Column(Integer, ForeignKey("purchase_orders.id"))
    received_date = Column(DateTime, default=datetime.datetime.utcnow)
    received_quantity = Column(Integer, default=0)
    received_amount = Column(Float, default=0.0)
    notes = Column(Text, nullable=True)

class ERPConnection(Base):
    """
    Stores user's ERP connection credentials.
    Enables switching between Python sample DB and real ERP without code changes.
    """
    __tablename__ = "erp_connections"
    id = Column(Integer, primary_key=True, index=True)
    connection_name = Column(String)  # e.g., 'Production SAP'
    erp_type = Column(String)  # 'python_db', 'sap', 'netsuite', 'custom'
    api_url = Column(String, nullable=True)
    api_key = Column(String, nullable=True)
    database_name = Column(String, nullable=True)
    username = Column(String, nullable=True)
    is_active = Column(Boolean, default=False)  # Only one active at a time
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_tested = Column(DateTime, nullable=True)
    test_status = Column(String, default='untested')  # 'success', 'failed', 'untested'
    test_error = Column(Text, nullable=True)
