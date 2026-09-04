"""Request Context Middleware for Nodal Sentinel.

Extracts, validates, or generates standard X-Request-ID headers,
populating the request_id context variable and injecting it into response headers.
"""
import time
import uuid
import re
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from backend.logging import request_id_ctx, logger

# Strict sanitized pattern for incoming request IDs
REQUEST_ID_REGEX = re.compile(r"^[a-zA-Z0-9_\-\.]{8,64}$")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Middleware enforcing end-to-end request correlation."""

    async def dispatch(self, request: Request, call_next) -> Response:
        raw_req_id = request.headers.get("X-Request-ID")

        if raw_req_id and REQUEST_ID_REGEX.match(raw_req_id):
            request_id = raw_req_id
        else:
            request_id = f"req_{uuid.uuid4().hex[:16]}"

        # Set context variable for duration of request
        token = request_id_ctx.set(request_id)
        start_time = time.perf_counter()

        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start_time) * 1000.0

            # Inject correlation and standard defensive security headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

            # Log non-health endpoint requests
            path = request.url.path
            if path not in ("/health", "/ready"):
                logger.info(
                    operation="HTTP_REQUEST",
                    message=f"{request.method} {path} - {response.status_code}",
                    duration_ms=duration_ms,
                    details={
                        "method": request.method,
                        "path": path,
                        "status_code": response.status_code,
                        "client_ip": request.client.host if request.client else None,
                    },
                )
            return response

        finally:
            request_id_ctx.reset(token)
