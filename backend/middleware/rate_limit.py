"""Rate Limiting and Abuse Protection Middleware for Expensive Endpoints.

Implements an in-memory sliding window rate limiter to protect compute-intensive
operations (e.g. dataset generation, full detection scans, evaluation runs).
"""
import time
from collections import defaultdict
from typing import Dict, List, Tuple
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from backend.logging import get_current_request_id, logger

# Rate limits: (max_requests, window_seconds)
RATE_LIMITED_ROUTES: Dict[str, Tuple[int, int]] = {
    "/data/generate": (10, 60),        # 10 generations per minute
    "/exceptions/detect": (30, 60),     # 30 full detection runs per minute
    "/evaluation/run": (20, 60),        # 20 benchmark runs per minute
    "/remediation/execute": (30, 60),   # 30 remediation executions per minute
    "/copilot/chat": (60, 60),          # 60 copilot queries per minute
}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Protects expensive endpoints from resource exhaustion."""

    def __init__(self, app):
        super().__init__(app)
        # client_ip -> route -> timestamps list
        self._request_history: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        limit_config = RATE_LIMITED_ROUTES.get(path)

        if not limit_config or request.method != "POST":
            return await call_next(request)

        client_ip = request.client.host if request.client else "127.0.0.1"

        # Allow testclient bypass for regular unit tests unless explicitly testing rate limits
        if client_ip == "testclient" and request.headers.get("X-Test-Rate-Limit") != "true":
            return await call_next(request)

        max_reqs, window_sec = limit_config
        now = time.time()

        # Clean old timestamps
        history = self._request_history[client_ip][path]
        self._request_history[client_ip][path] = [t for t in history if now - t < window_sec]
        active_history = self._request_history[client_ip][path]

        if len(active_history) >= max_reqs:
            logger.warning(
                operation="RATE_LIMIT_EXCEEDED",
                message=f"Rate limit exceeded on {path} for IP {client_ip}",
                details={"client_ip": client_ip, "path": path, "limit": max_reqs, "window": window_sec},
            )
            req_id = get_current_request_id()
            return JSONResponse(
                status_code=429,
                content={
                    "error": "RATE_LIMIT_EXCEEDED",
                    "message": f"Too many requests to {path}. Limit is {max_reqs} requests per {window_sec}s.",
                    "request_id": req_id,
                    "details": {"retry_after_seconds": window_sec},
                },
                headers={"X-Request-ID": req_id, "Retry-After": str(window_sec)},
            )

        active_history.append(now)
        return await call_next(request)
