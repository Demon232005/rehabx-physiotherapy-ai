"""Basic in-memory rate limiting.

A sliding-window limiter keyed by client IP and endpoint (each
``rate_limit(...)`` call gets its own bucket so different endpoints do
not consume each other's quota). Suitable for a single-process
prototype; swap for Redis-based limiting in production.

Set ``RATE_LIMIT_ENABLED=false`` (e.g. in tests or behind a proxy that
already throttles) to bypass limiting entirely.
"""
from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.core.config import get_settings

_limits: dict[str, deque] = defaultdict(deque)


def rate_limit(max_requests: int = 30, window_seconds: int = 60):
    bucket_id = uuid.uuid4().hex

    def dependency(request: Request) -> None:
        if not get_settings().rate_limit_enabled:
            return
        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        window = _limits[f"{client_ip}:{bucket_id}"]
        while window and window[0] <= now - window_seconds:
            window.popleft()
        if len(window) >= max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded, try again later",
            )
        window.append(now)

    return dependency
