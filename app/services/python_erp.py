"""
Python ERP Client — Local SQLite-backed ERP implementation.

CRITICAL: Uses short-lived sessions for EVERY operation.
This ensures reads always see the latest committed data,
enabling real-time visibility across agent, UI, and APIs.

NO long-lived sessions. NO stale reads.
"""

from ..database import SessionLocal
from .. import models
import logging

logger = logging.getLogger("PythonERP")


class PythonERPClient:
    """
    Local ERP implementation using SQLite database.
    
    Each method creates and closes its own DB session.
    This guarantees every read sees the latest committed state,
    which is critical for simultaneous visibility between
    the agent, UI, and API components.
    """

    def get_vendors(self):
        """Get all active vendors from local DB."""
        db = SessionLocal()
        try:
            vendors = db.query(models.Vendor).filter(
                models.Vendor.active == True
            ).all()
            result = [{"id": v.id, "name": v.name, "email": v.email} for v in vendors]
            logger.info(f"PythonERP: Returned {len(result)} vendors")
            return result
        finally:
            db.close()

    def get_vendor_by_id(self, vendor_id: int):
        """Get a single vendor by ID."""
        db = SessionLocal()
        try:
            v = db.query(models.Vendor).filter(models.Vendor.id == vendor_id).first()
            if v:
                return {"id": v.id, "name": v.name, "email": v.email}
            return None
        finally:
            db.close()

    def get_vendor_alias(self, raw_name: str):
        """
        Look up a vendor alias by raw name.
        Returns {vendor_id, confidence} if found, else None.
        """
        db = SessionLocal()
        try:
            alias = db.query(models.VendorAlias).filter(
                models.VendorAlias.alias_name == raw_name
            ).first()
            if alias:
                logger.info(f"PythonERP: Alias hit: '{raw_name}' → vendor_id={alias.vendor_id} (confidence={alias.confidence})")
                return {
                    "vendor_id": alias.vendor_id,
                    "confidence": alias.confidence,
                    "learned_from_invoice_id": alias.learned_from_invoice_id
                }
            logger.info(f"PythonERP: No alias for '{raw_name}'")
            return None
        finally:
            db.close()

    def store_vendor_alias(self, alias_name: str, vendor_id: int, invoice_id: int = None):
        """
        Persist a learned vendor alias.
        Commits immediately — visible to all components instantly.
        Returns True if stored, False if already exists.
        """
        db = SessionLocal()
        try:
            existing = db.query(models.VendorAlias).filter(
                models.VendorAlias.alias_name == alias_name
            ).first()
            if existing:
                logger.info(f"PythonERP: Alias '{alias_name}' already exists")
                return False

            alias = models.VendorAlias(
                alias_name=alias_name,
                vendor_id=vendor_id,
                confidence=100,
                learned_from_invoice_id=invoice_id
            )
            db.add(alias)
            db.commit()
            logger.info(f"PythonERP: STORED alias '{alias_name}' → vendor_id={vendor_id}")
            return True
        finally:
            db.close()

    def get_purchase_orders(self, vendor_id=None):
        """Get purchase orders, optionally filtered by vendor."""
        db = SessionLocal()
        try:
            query = db.query(models.PurchaseOrder)
            if vendor_id:
                query = query.filter(models.PurchaseOrder.vendor_id == vendor_id)
            pos = query.all()
            result = [
                {
                    "id": p.id,
                    "po_number": p.po_number,
                    "vendor_id": p.vendor_id,
                    "total_amount": p.total_amount,
                    "status": p.status,
                    "quantity": p.quantity,
                }
                for p in pos
            ]
            logger.info(f"PythonERP: Returned {len(result)} POs")
            return result
        finally:
            db.close()

    def get_goods_receipts(self, po_id):
        """Get goods receipts for a specific purchase order."""
        db = SessionLocal()
        try:
            receipts = db.query(models.GoodsReceipt).filter(
                models.GoodsReceipt.purchase_order_id == po_id
            ).all()
            result = [
                {
                    "id": r.id,
                    "purchase_order_id": r.purchase_order_id,
                    "received_date": r.received_date.isoformat() if r.received_date else None,
                    "received_quantity": r.received_quantity,
                    "received_amount": r.received_amount,
                }
                for r in receipts
            ]
            logger.info(f"PythonERP: Returned {len(result)} receipts for PO {po_id}")
            return result
        finally:
            db.close()

    def test_connection(self):
        """Test that local DB is accessible."""
        db = SessionLocal()
        try:
            count = db.query(models.Vendor).count()
            return {"success": True, "message": f"Python Sample DB active — {count} vendors loaded"}
        except Exception as e:
            return {"success": False, "message": str(e)}
        finally:
            db.close()
