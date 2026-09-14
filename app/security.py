from __future__ import annotations

import hmac
import time
from collections import deque
from threading import Lock

from fastapi import HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings

_bearer = HTTPBearer(auto_error=False)
_security_dependency = Security(_bearer)


class SlidingWindowRateLimiter:
    """Small in-memory limiter suitable for the single-worker MVP deployment."""

    def __init__(self, requests_per_minute: int) -> None:
        self.limit = requests_per_minute
        self._hits: deque[float] = deque()
        self._lock = Lock()

    def allow(self) -> bool:
        now = time.monotonic()
        cutoff = now - 60.0
        with self._lock:
            while self._hits and self._hits[0] <= cutoff:
                self._hits.popleft()
            if len(self._hits) >= self.limit:
                return False
            self._hits.append(now)
            return True


def get_settings_from_request(request: Request) -> Settings:
    return request.app.state.settings


async def require_api_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = _security_dependency,
) -> None:
    settings = get_settings_from_request(request)
    if (
        credentials is None
        or credentials.scheme.lower() != "bearer"
        or not hmac.compare_digest(credentials.credentials, settings.api_token)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    limiter: SlidingWindowRateLimiter = request.app.state.rate_limiter
    if not limiter.allow():
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": "60"},
        )
