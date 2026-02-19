"""
Analytics Service - Metrics Aggregation Engine

Aggregates data from invoices, conversation history, and events to provide
real-time system insights.
"""

import logging
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from .. import models
from ..agent.ai_client import get_ai_client

logger = logging.getLogger(__name__)

class AnalyticsService:
    @staticmethod
    def get_ai_metrics(db: Session) -> Dict[str, Any]:
        """
        Aggregate AI costs, token usage, and model distribution.
        """
        try:
            # Query conversation messages for metadata
            messages = db.query(models.ConversationMessage).all()
            
            total_cost = 0.0
            total_tokens = 0
            model_counts = {}
            fallback_count = 0
            
            for msg in messages:
                if msg.role == "assistant" and msg.message_metadata:
                    meta = msg.message_metadata
                    total_cost += meta.get("cost_usd", 0.0)
                    total_tokens += meta.get("tokens", 0)
                    
                    model = meta.get("model", "unknown")
                    model_counts[model] = model_counts.get(model, 0) + 1
                    
                    if meta.get("fallback_used", False):
                        fallback_count += 1
            
            # Health check from live client
            client = get_ai_client()
            health = client.get_stats()
            
            return {
                "total_cost_usd": round(total_cost, 4),
                "total_tokens": total_tokens,
                "model_distribution": model_counts,
                "fallback_rate": round(fallback_count / max(len(messages)//2, 1), 2),
                "active_stats": health
            }
        except Exception as e:
            logger.error(f"Error aggregating AI metrics: {e}")
            return {"error": str(e)}

    @staticmethod
    def get_invoice_stats(db: Session) -> Dict[str, Any]:
        """
        Calculate invoice throughput and accuracy metrics.
        """
        try:
            total_count = db.query(models.Invoice).count()
            status_counts = db.query(
                models.Invoice.status, func.count(models.Invoice.id)
            ).group_by(models.Invoice.status).all()
            
            status_map = {status: count for status, count in status_counts}
            
            # Avg confidence
            avg_confidence = db.query(func.avg(models.Invoice.confidence_score)).scalar() or 0.0
            
            # Suspicious rate
            suspicious_count = db.query(models.Invoice).filter(models.Invoice.is_suspicious == True).count()
            
            return {
                "total_invoices": total_count,
                "by_status": status_map,
                "average_confidence": round(float(avg_confidence), 2),
                "suspicious_count": suspicious_count,
                "fraud_rate": round(suspicious_count / max(total_count, 1), 2)
            }
        except Exception as e:
            logger.error(f"Error aggregating invoice stats: {e}")
            return {"error": str(e)}

    @staticmethod
    def get_dashboard_overview(db: Session) -> Dict[str, Any]:
        """
        Consolidated overview for the main dashboard.
        """
        ai = AnalyticsService.get_ai_metrics(db)
        inv = AnalyticsService.get_invoice_stats(db)
        
        # System health indicator
        recent_events = db.query(models.Event).order_by(models.Event.timestamp.desc()).limit(5).all()
        
        return {
            "summary": {
                "revenue_managed": round(db.query(func.sum(models.Invoice.total_amount)).scalar() or 0.0, 2),
                "ai_cost": ai.get("total_cost_usd", 0.0),
                "pending_approvals": inv.get("by_status", {}).get("PENDING_APPROVAL", 0)
            },
            "ai_performance": ai,
            "invoice_processing": inv,
            "system_health": "Healthy" if not ai.get("error") else "Degraded",
            "recent_activity": [
                {"id": e.id, "type": e.event_type, "time": e.timestamp.isoformat()} 
                for e in recent_events
            ]
        }
