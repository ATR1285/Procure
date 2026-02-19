"""
Monitoring Middleware and Prometheus instrumentation for Procure-IQ.

Captures request latencies, status codes, and AI model usage metrics.
"""

import time
import logging
from typing import Callable
from fastapi import Request, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# --- Metrics Definition ---

try:
    # Request Metrics
    REQUEST_COUNT = Counter(
        "api_request_total",
        "Total count of HTTP requests",
        ["method", "path", "status_code"]
    )

    REQUEST_LATENCY = Histogram(
        "api_request_latency_seconds",
        "Latency of HTTP requests in seconds",
        ["method", "path"]
    )

    # AI Client Metrics
    AI_INVOCATIONS = Counter(
        "ai_model_invocations_total",
        "Total count of AI model calls",
        ["model", "fallback_used"]
    )

    AI_TOKENS = Counter(
        "ai_tokens_total",
        "Total tokens consumed",
        ["model", "token_type"] # token_type: input, output
    )

    AI_COST = Counter(
        "ai_cost_usd_total",
        "Total AI cost in USD",
        ["model"]
    )
except ValueError:
    # Metrics already registered
    from prometheus_client import REGISTRY
    REQUEST_COUNT = REGISTRY._names_to_collectors["api_request_total"]
    REQUEST_LATENCY = REGISTRY._names_to_collectors["api_request_latency_seconds"]
    AI_INVOCATIONS = REGISTRY._names_to_collectors["ai_model_invocations_total"]
    AI_TOKENS = REGISTRY._names_to_collectors["ai_tokens_total"]
    AI_COST = REGISTRY._names_to_collectors["ai_cost_usd_total"]


# --- Middleware Implementation ---

class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Don't monitor /metrics itself to avoid noise
        if request.url.path.rstrip("/") == "/metrics":
            return await call_next(request)

        method = request.method
        path = request.url.path



        
        start_time = time.time()
        
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            status_code = 500
            raise e
        finally:
            latency = time.time() - start_time
            
            # Record metrics
            REQUEST_COUNT.labels(method=method, path=path, status_code=status_code).inc()
            REQUEST_LATENCY.labels(method=method, path=path).observe(latency)
            
        return response

# --- Helper functions ---

def get_metrics():
    """Generates the latest metrics scrapable by Prometheus."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

def instrument_ai_call(model: str, tokens: int, cost: float, fallback: bool):
    """
    Update Prometheus metrics for an AI call.
    """
    AI_INVOCATIONS.labels(model=model, fallback_used=str(fallback)).inc()
    AI_TOKENS.labels(model=model, token_type="total").inc(tokens)
    AI_COST.labels(model=model).inc(cost)
    logger.debug(f"Metrics updated: {model}, cost={cost}")
