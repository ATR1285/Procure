from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, ForeignKey, JSON, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime

SQLALCHEMY_DATABASE_URL = "sqlite:///./procure_iq.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class Vendor(Base):
    __tablename__ = "vendors"
    id = Column(Integer, primary_key=True, index=True)
    odoo_id = Column(Integer, unique=True, index=True)
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

class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String, index=True) # INVOICE_RECEIVED, VENDOR_LEARNED, STOCK_CHECK, SMS_APPROVED
    payload = Column(JSON)
    status = Column(String, default="PENDING") # PENDING, PROCESSING, COMPLETED, FAILED
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)

class Inventory(Base):
    __tablename__ = "inventory"
    id = Column(Integer, primary_key=True, index=True)
    item_name = Column(String, index=True)
    quantity = Column(Integer, default=0)
    limit_threshold = Column(Integer, default=50)
    supplier_id = Column(Integer, ForeignKey("vendors.id"))
    last_checked = Column(DateTime, default=datetime.datetime.utcnow)

class SMSLog(Base):
    __tablename__ = "sms_logs"
    id = Column(Integer, primary_key=True, index=True)
    recipient_number = Column(String)
    message_body = Column(Text)
    status = Column(String, default="SENT")
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    related_item_id = Column(Integer, ForeignKey("inventory.id"), nullable=True)
