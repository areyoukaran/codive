from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

log = logging.getLogger("codive.request")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Every response gets an X-Request-Id (generated, or carried through if
    the caller already set one) and every log line for that request can be
    correlated by it. Structured logging per §18 of the blueprint, kept to
    one middleware instead of scattered logger calls."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        start = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.monotonic() - start) * 1000)
            log.exception(
                "unhandled error request_id=%s method=%s path=%s duration_ms=%s",
                request_id, request.method, request.url.path, duration_ms,
            )
            return JSONResponse(
                {"error": "internal_error", "message": "Something went wrong on our end.", "request_id": request_id},
                status_code=500,
                headers={"X-Request-Id": request_id},
            )
        duration_ms = round((time.monotonic() - start) * 1000)
        log.info(
            "request_id=%s method=%s path=%s status=%s duration_ms=%s",
            request_id, request.method, request.url.path, response.status_code, duration_ms,
        )
        response.headers["X-Request-Id"] = request_id
        return response
