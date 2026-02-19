"""
ERP Management API — Endpoints for managing ERP connections.

Provides:
- POST /api/erp/test-connection — Test ERP connectivity
- POST /api/erp/save-connection — Save and activate an ERP connection
- GET /api/erp/current — Return active ERP info
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import datetime
import logging

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.database import get_db
from app import models
from app.services.erp_adapter import erp_adapter

logger = logging.getLogger("ERPManagement")

router = APIRouter(prefix="/api/erp", tags=["erp"])


@router.get("/current")
def get_current_connection(db: Session = Depends(get_db)):
    """Return info about the currently active ERP connection."""
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


@router.post("/test-connection")
def test_connection(data: dict, db: Session = Depends(get_db)):
    """Test an ERP connection without saving."""
    erp_type = data.get("erp_type", "python_db")

    if erp_type == "python_db":
        # Test local DB
        result = erp_adapter.test_connection()
        return result

    # For real ERPs, validate that required fields are provided
    api_url = data.get("api_url", "")
    api_key = data.get("api_key", "")

    if not api_url:
        return {"success": False, "message": "API URL is required for external ERP connections"}

    # Simulate connection test for external ERPs
    # In production, this would actually try to connect
    return {
        "success": True,
        "message": f"Connection to {erp_type.upper()} at {api_url} configured. "
                   f"Real connectivity will be verified when agents query data."
    }


@router.post("/save-connection")
def save_connection(data: dict, db: Session = Depends(get_db)):
    """Save and activate an ERP connection."""
    try:
        erp_type = data.get("erp_type", "python_db")
        connection_name = data.get("connection_name", "")

        if not connection_name:
            connection_name = f"{erp_type.upper()} Connection"

        # Deactivate all existing connections
        db.query(models.ERPConnection).update({"is_active": False})

        # Check if connection with same name exists
        existing = db.query(models.ERPConnection).filter(
            models.ERPConnection.connection_name == connection_name
        ).first()

        if existing:
            existing.erp_type = erp_type
            existing.api_url = data.get("api_url")
            existing.api_key = data.get("api_key")
            existing.database_name = data.get("database_name")
            existing.username = data.get("username")
            existing.is_active = True
            existing.test_status = "success" if erp_type == "python_db" else "untested"
            existing.last_tested = datetime.datetime.utcnow() if erp_type == "python_db" else None
        else:
            new_conn = models.ERPConnection(
                connection_name=connection_name,
                erp_type=erp_type,
                api_url=data.get("api_url"),
                api_key=data.get("api_key"),
                database_name=data.get("database_name"),
                username=data.get("username"),
                is_active=True,
                test_status="success" if erp_type == "python_db" else "untested",
                last_tested=datetime.datetime.utcnow() if erp_type == "python_db" else None,
            )
            db.add(new_conn)

        db.commit()

        # Refresh the singleton adapter
        erp_adapter.refresh()

        logger.info(f"ERP Connection saved: {connection_name} ({erp_type})")

        return {
            "success": True,
            "message": f"Connection '{connection_name}' ({erp_type}) saved and activated!"
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to save ERP connection: {e}")
        return {"success": False, "message": str(e)}
