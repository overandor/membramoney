"""
CleanStat Infrastructure - Prometheus Metrics
Production monitoring with Prometheus
"""
from prometheus_client import Counter, Histogram, generate_latest
from fastapi import Response
import time

REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
REQUEST_LATENCY = Histogram('http_request_duration_seconds', 'HTTP request latency', ['method', 'endpoint'])

async def metrics_middleware(request, call_next):
    """Middleware to track HTTP request metrics"""
    start = time.time()
    response = await call_next(request)
    REQUEST_COUNT.labels(request.method, request.url.path, response.status_code).inc()
    REQUEST_LATENCY.labels(request.method, request.url.path).observe(time.time() - start)
    return response

async def get_metrics():
    """Endpoint to expose Prometheus metrics"""
    return Response(generate_latest(), media_type="text/plain")
