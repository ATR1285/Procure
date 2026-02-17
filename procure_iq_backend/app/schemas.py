from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime

class VendorBase(BaseModel):
    name: str
    odoo_id: Optional[int] = None
    email: Optional[str] = None

class Vendor(VendorBase):
    id: int
    active: bool

    class Config:
        from_attributes = True

class InvoiceBase(BaseModel):
    invoice_number: str
    total_amount: float
    vendor_id: Optional[int] = None
    invoice_date: Optional[datetime] = None

class InvoiceCreate(InvoiceBase):
    pass

class Invoice(InvoiceBase):
    id: int
    status: str
    confidence_score: Optional[int] = None
    reasoning_note: Optional[str] = None
    is_suspicious: bool = False
    extracted_data: dict = {}
    audit_trail: List[dict] = []

    class Config:
        from_attributes = True

class EventBase(BaseModel):
    event_type: str
    payload: dict

class EventCreate(EventBase):
    pass

class Event(EventBase):
    id: int
    status: str
    created_at: datetime
    processed_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class SimulationTrigger(BaseModel):
    vendorName: str
    invoiceAmount: float
    invoiceNumber: str
