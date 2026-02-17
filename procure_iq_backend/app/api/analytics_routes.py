"""
Analytics API Routes

Exposes system metrics and performance data for dashboard visualization.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..services.analytics_service import AnalyticsService
from typing import Dict, Any

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

@router.get("/overview")
async def get_overview(db: Session = Depends(get_db)):
    """
    Get consolidated system overview metrics.
    """
    return AnalyticsService.get_dashboard_overview(db)

@router.get("/ai")
async def get_ai_stats(db: Session = Depends(get_db)):
    """
    Get detailed AI cost and model performance statistics.
    """
    return AnalyticsService.get_ai_metrics(db)

@router.get("/invoices")
async def get_invoice_stats(db: Session = Depends(get_db)):
    """
    Get statistics related to invoice processing and accuracy.
    """
    return AnalyticsService.get_invoice_stats(db)
