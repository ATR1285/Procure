"""
ERP Adapter — Strategy pattern for pluggable ERP connections.

ALL ERP data access from agent code MUST go through this adapter.
Direct DB queries to ERP models (Vendor, VendorAlias, PO, Receipt)
are FORBIDDEN in agent code.

Flow: Agent → ERPAdapter → ERPClient (PythonERP / SAP / NetSuite)
"""

from .python_erp import PythonERPClient
from ..database import SessionLocal
from .. import models
import logging
import datetime

logger = logging.getLogger("ERPAdapter")


class ERPAdapter:
    """
    Adapter that routes ALL ERP calls to the active backend.
    
    Default: PythonERPClient (local SQLite sample data)
    Optional: SAPERPClient, NetSuiteERPClient, etc.
    
    RULE: No agent code may bypass this adapter.
    """

    def __init__(self):
        self.client = self._get_active_client()

    def _get_active_client(self):
        """Get the currently active ERP connection and return the appropriate client."""
        db = SessionLocal()
        try:
            active = db.query(models.ERPConnection).filter(
                models.ERPConnection.is_active == True
            ).first()

            if not active or active.erp_type == "python_db":
                logger.info("ERPAdapter → PythonERPClient (local SQLite)")
                return PythonERPClient()

            if active.erp_type == "sap":
                logger.info(f"ERPAdapter → SAP at {active.api_url} (fallback to PythonERP)")
                return PythonERPClient()

            if active.erp_type == "netsuite":
                logger.info(f"ERPAdapter → NetSuite at {active.api_url} (fallback to PythonERP)")
                return PythonERPClient()

            logger.warning(f"ERPAdapter → Unknown type '{active.erp_type}', using PythonERP")
            return PythonERPClient()
        finally:
            db.close()

    def refresh(self):
        """Refresh the active client (call after connection changes)."""
        self.client = self._get_active_client()

    # ── Vendor Operations ──────────────────────────────────────

    def get_vendors(self):
        """Get vendors from the active ERP backend."""
        return self.client.get_vendors()

    def get_vendor_by_id(self, vendor_id: int):
        """Get a single vendor by ID."""
        return self.client.get_vendor_by_id(vendor_id)

    # ── Alias / Learning Operations ────────────────────────────

    def get_vendor_alias(self, raw_name: str):
        """
        Look up a vendor alias.
        Returns dict {vendor_id, confidence} if found, else None.
        """
        return self.client.get_vendor_alias(raw_name)

    def store_vendor_alias(self, alias_name: str, vendor_id: int, invoice_id: int = None):
        """
        Persist a learned vendor alias after human approval.
        Returns True if stored, False if already exists.
        """
        return self.client.store_vendor_alias(alias_name, vendor_id, invoice_id)

    # ── PO / Receipt Operations ────────────────────────────────

    def get_purchase_orders(self, vendor_id=None):
        """Get purchase orders from the active ERP backend."""
        return self.client.get_purchase_orders(vendor_id)

    def get_goods_receipts(self, po_id):
        """Get goods receipts for a PO from the active ERP backend."""
        return self.client.get_goods_receipts(po_id)

    # ── Connection Management ──────────────────────────────────

    def test_connection(self):
        """Test the active ERP connection."""
        return self.client.test_connection()

    def get_active_info(self):
        """Return info about the currently active ERP connection."""
        db = SessionLocal()
        try:
            active = db.query(models.ERPConnection).filter(
                models.ERPConnection.is_active == True
            ).first()
            if active:
                return {
                    "id": active.id,
                    "connection_name": active.connection_name,
                    "erp_type": active.erp_type,
                    "api_url": active.api_url,
                    "is_active": active.is_active,
                    "test_status": active.test_status,
                    "last_tested": active.last_tested.isoformat() if active.last_tested else None,
                }
            return {
                "connection_name": "Python Sample DB",
                "erp_type": "python_db",
                "is_active": True,
                "test_status": "success",
            }
        finally:
            db.close()


# Singleton instance — all agent code imports this
erp_adapter = ERPAdapter()
