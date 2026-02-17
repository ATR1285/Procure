"""
Core Tools for Procure-IQ AI Agent

Implements essential tools for system interaction:
- get_vendor_info: Fetch vendor details
- get_invoice_status: Check invoice processing status
- approve_invoice: Manually approve invoices
- get_inventory_status: Monitor stock levels
"""

from typing import Optional, Dict, List, Any
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.database import SessionLocal
from app import models
from app.tools import register_tool
import logging

logger = logging.getLogger(__name__)


@register_tool(
    name="get_vendor_info",
    description="Fetch detailed vendor information by ID or name. Returns vendor details, aliases, and transaction history.",
    parameters={
        "type": "object",
        "properties": {
            "vendor_id": {
                "type": "integer",
                "description": "Vendor database ID (optional if vendor_name provided)"
            },
            "vendor_name": {
                "type": "string",
                "description": "Vendor name for fuzzy matching (optional if vendor_id provided)"
            }
        }
    }
)
def get_vendor_info(vendor_id: Optional[int] = None, vendor_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch vendor details by ID or name.
    
    Args:
        vendor_id: Vendor database ID
        vendor_name: Vendor name (fuzzy match)
    
    Returns:
        {
            "id": int,
            "name": str,
            "email": str,
            "active": bool,
            "aliases": [str],
            "invoice_count": int,
            "total_spent": float
        }
    """
    db = SessionLocal()
    try:
        # Find vendor
        if vendor_id:
            vendor = db.query(models.Vendor).filter(models.Vendor.id == vendor_id).first()
        elif vendor_name:
            # Fuzzy match on name
            vendor = db.query(models.Vendor).filter(
                models.Vendor.name.ilike(f"%{vendor_name}%")
            ).first()
        else:
            return {"error": "Either vendor_id or vendor_name must be provided"}
        
        if not vendor:
            return {"error": "Vendor not found"}
        
        # Get aliases
        aliases = db.query(models.VendorAlias).filter(
            models.VendorAlias.vendor_id == vendor.id
        ).all()
        
        # Get invoice stats
        invoices = db.query(models.Invoice).filter(
            models.Invoice.vendor_id == vendor.id
        ).all()
        
        total_spent = sum(inv.total_amount for inv in invoices)
        
        return {
            "id": vendor.id,
            "name": vendor.name,
            "email": vendor.email,
            "active": vendor.active,
            "aliases": [alias.alias_name for alias in aliases],
            "invoice_count": len(invoices),
            "total_spent": total_spent
        }
    
    finally:
        db.close()


@register_tool(
    name="get_invoice_status",
    description="Check the processing status of an invoice. Returns current status, confidence score, and complete audit trail.",
    parameters={
        "type": "object",
        "properties": {
            "invoice_number": {
                "type": "string",
                "description": "Invoice number to check"
            }
        },
        "required": ["invoice_number"]
    }
)
def get_invoice_status(invoice_number: str) -> Dict[str, Any]:
    """
    Check invoice processing status.
    
    Args:
        invoice_number: Invoice number to check
    
    Returns:
        {
            "invoice_number": str,
            "status": str,
            "vendor": str,
            "amount": float,
            "confidence_score": int,
            "audit_trail": [dict],
            "created_at": str,
            "updated_at": str
        }
    """
    db = SessionLocal()
    try:
        invoice = db.query(models.Invoice).filter(
            models.Invoice.invoice_number == invoice_number
        ).first()
        
        if not invoice:
            return {"error": f"Invoice {invoice_number} not found"}
        
        # Get vendor name
        vendor_name = "Unknown"
        if invoice.vendor_id:
            vendor = db.query(models.Vendor).filter(models.Vendor.id == invoice.vendor_id).first()
            if vendor:
                vendor_name = vendor.name
        
        return {
            "invoice_number": invoice.invoice_number,
            "status": invoice.status,
            "vendor": vendor_name,
            "vendor_id": invoice.vendor_id,
            "amount": invoice.total_amount,
            "currency": invoice.currency,
            "confidence_score": invoice.confidence_score,
            "reasoning": invoice.reasoning_note,
            "is_suspicious": invoice.is_suspicious,
            "audit_trail": invoice.audit_trail,
            "created_at": invoice.invoice_date.isoformat() if invoice.invoice_date else None
        }
    
    finally:
        db.close()


@register_tool(
    name="approve_invoice",
    description="Manually approve an invoice. Updates status to APPROVED and adds audit trail entry.",
    parameters={
        "type": "object",
        "properties": {
            "invoice_number": {
                "type": "string",
                "description": "Invoice number to approve"
            },
            "reason": {
                "type": "string",
                "description": "Optional reason for manual approval"
            }
        },
        "required": ["invoice_number"]
    }
)
def approve_invoice(invoice_number: str, reason: Optional[str] = None) -> Dict[str, Any]:
    """
    Manually approve an invoice.
    
    Args:
        invoice_number: Invoice number to approve
        reason: Optional approval reason
    
    Returns:
        {
            "success": bool,
            "message": str,
            "invoice_number": str,
            "new_status": str
        }
    """
    db = SessionLocal()
    try:
        invoice = db.query(models.Invoice).filter(
            models.Invoice.invoice_number == invoice_number
        ).first()
        
        if not invoice:
            return {
                "success": False,
                "error": f"Invoice {invoice_number} not found"
            }
        
        # Check if already approved
        if invoice.status == "APPROVED":
            return {
                "success": False,
                "error": f"Invoice {invoice_number} is already approved"
            }
        
        # Update status
        old_status = invoice.status
        invoice.status = "APPROVED"
        
        # Add audit trail
        from sqlalchemy.orm.attributes import flag_modified
        from datetime import datetime
        
        invoice.audit_trail.append({
            "t": "manual_approval",
            "m": reason or "Manually approved via tool",
            "old_status": old_status,
            "timestamp": datetime.now().isoformat()
        })
        flag_modified(invoice, "audit_trail")
        
        db.commit()
        
        return {
            "success": True,
            "message": f"Invoice {invoice_number} approved successfully",
            "invoice_number": invoice_number,
            "old_status": old_status,
            "new_status": "APPROVED"
        }
    
    except Exception as e:
        db.rollback()
        return {
            "success": False,
            "error": str(e)
        }
    
    finally:
        db.close()


@register_tool(
    name="get_inventory_status",
    description="Check inventory levels. Can filter by item name or show only low stock items.",
    parameters={
        "type": "object",
        "properties": {
            "item_name": {
                "type": "string",
                "description": "Specific item name to check (optional, fuzzy match)"
            },
            "low_stock_only": {
                "type": "boolean",
                "description": "Only return items below reorder threshold"
            }
        }
    }
)
def get_inventory_status(item_name: Optional[str] = None, low_stock_only: bool = False) -> Dict[str, Any]:
    """
    Check inventory levels.
    
    Args:
        item_name: Specific item to check (optional)
        low_stock_only: Only return low stock items
    
    Returns:
        {
            "items": [
                {
                    "name": str,
                    "quantity": int,
                    "reorder_threshold": int,
                    "reorder_quantity": int,
                    "supplier": str,
                    "unit_price": float
                }
            ],
            "total_items": int,
            "low_stock_count": int
        }
    """
    db = SessionLocal()
    try:
        # Build query
        query = db.query(models.InventoryItem)
        
        if item_name:
            query = query.filter(models.InventoryItem.name.ilike(f"%{item_name}%"))
        
        if low_stock_only:
            query = query.filter(models.InventoryItem.quantity <= models.InventoryItem.reorder_threshold)
        
        items = query.all()
        
        # Build response
        item_list = []
        for item in items:
            # Get supplier name
            supplier_name = "Unknown"
            if item.supplier_id:
                supplier = db.query(models.Vendor).filter(models.Vendor.id == item.supplier_id).first()
                if supplier:
                    supplier_name = supplier.name
            
            item_list.append({
                "id": item.id,
                "name": item.name,
                "sku": item.sku,
                "quantity": item.quantity,
                "reorder_threshold": item.reorder_threshold,
                "reorder_quantity": item.reorder_quantity,
                "supplier": supplier_name,
                "supplier_id": item.supplier_id,
                "unit_price": item.unit_price,
                "is_low_stock": item.quantity <= item.reorder_threshold
            })
        
        # Count low stock items
        low_stock_count = sum(1 for item in item_list if item["is_low_stock"])
        
        return {
            "items": item_list,
            "total_items": len(item_list),
            "low_stock_count": low_stock_count
        }
    
    finally:
        db.close()


# Auto-register all tools on import
logger.info("Core tools registered successfully")
