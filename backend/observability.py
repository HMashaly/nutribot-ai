"""
observability.py — logging, request correlation, and tracing for NutriBot.

Three pieces, all opt-in via config / environment:

1. configure_logging()      — routes loguru to stderr as either human-readable
                              text (dev) or structured JSON (prod), at the
                              configured level.
2. configure_langsmith()    — enables LangChain/LangGraph tracing to LangSmith
                              when LANGCHAIN_TRACING_V2 is set and an API key is
                              present. No-op otherwise.
3. RequestContextMiddleware — assigns every request an ID, binds it to the log
                              context, records latency, and stamps it (plus a
                              few baseline security headers) onto the response.

The request ID is also exposed via `current_request_id()` so downstream code
(e.g. the agent run) can tag traces with the same correlation ID.
"""

from __future__ import annotations

import os
import sys
import time
import uuid
from contextvars import ContextVar

from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from config import settings

# Correlation ID for the in-flight request. Defaults to "-" outside a request.
_request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")

REQUEST_ID_HEADER = "X-Request-ID"

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}


def current_request_id() -> str:
    """Return the correlation ID for the current request, or '-' if none."""
    return _request_id_ctx.get()


def configure_logging() -> None:
    """Configure loguru: single stderr sink, level + format driven by settings."""
    logger.remove()
    if settings.log_format.lower() == "json":
        logger.add(sys.stderr, level=settings.log_level.upper(), serialize=True, enqueue=True)
    else:
        logger.add(
            sys.stderr,
            level=settings.log_level.upper(),
            enqueue=True,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> "
                "<level>{level: <8}</level> "
                "<cyan>{extra[request_id]}</cyan> "
                "<level>{message}</level>"
            ),
        )
    # Make request_id always present so the format string never KeyErrors.
    logger.configure(extra={"request_id": "-"})


def configure_langsmith() -> None:
    """Enable LangSmith tracing when configured; otherwise leave it off."""
    if not settings.langchain_tracing_v2 or not settings.langchain_api_key:
        logger.info("LangSmith tracing disabled")
        return

    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
    os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project
    os.environ["LANGCHAIN_ENDPOINT"] = settings.langchain_endpoint
    logger.info("LangSmith tracing enabled (project={})", settings.langchain_project)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assign a request ID, log the request lifecycle, and harden the response."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        token = _request_id_ctx.set(request_id)
        start = time.perf_counter()

        with logger.contextualize(request_id=request_id):
            logger.info("→ {} {}", request.method, request.url.path)
            try:
                response: Response = await call_next(request)
            except Exception:
                duration_ms = (time.perf_counter() - start) * 1000
                logger.exception(
                    "✗ {} {} failed after {:.1f}ms",
                    request.method,
                    request.url.path,
                    duration_ms,
                )
                raise
            finally:
                _request_id_ctx.reset(token)

            duration_ms = (time.perf_counter() - start) * 1000
            logger.info(
                "← {} {} {} {:.1f}ms",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )

        response.headers[REQUEST_ID_HEADER] = request_id
        for header, value in _SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        return response
