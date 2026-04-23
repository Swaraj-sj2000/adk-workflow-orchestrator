from __future__ import annotations

import os
from collections import defaultdict, deque
from time import time
from typing import Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, requests_per_window: int = 120, window_seconds: int = 60):
        super().__init__(app)
        self.requests_per_window = requests_per_window
        self.window_seconds = window_seconds
        self._buckets: dict = defaultdict(deque)  # in-memory fallback
        self._redis: Optional[object] = None
        self._skip_prefixes = ("/docs", "/redoc", "/openapi.json", "/")

        redis_url = os.getenv("REDIS_URL", "")
        if redis_url:
            try:
                import redis as _redis
                client = _redis.from_url(redis_url, decode_responses=True)
                client.ping()
                self._redis = client
            except Exception:
                self._redis = None

    def _auth_limit(self) -> int:
        return min(self.requests_per_window, 30)

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self._skip_prefixes and request.method == "GET":
            return await call_next(request)

        client_host = request.client.host if request.client else "unknown"
        is_auth = request.url.path.startswith("/auth") or request.url.path.startswith("/accept-invite")
        path_key = "auth" if is_auth else request.url.path
        key = f"{client_host}:{path_key}"
        limit = self._auth_limit() if is_auth else self.requests_per_window

        if self._redis is not None:
            allowed = self._redis_check(key, limit)
        else:
            allowed = self._memory_check(key, limit)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please retry shortly."},
            )
        return await call_next(request)

    def _redis_check(self, key: str, limit: int) -> bool:
        try:
            import redis as _redis
            now = time()
            window_start = now - self.window_seconds
            pipe = self._redis.pipeline()  # type: ignore[union-attr]
            pipe.zremrangebyscore(key, "-inf", window_start)
            pipe.zadd(key, {str(now): now})
            pipe.zcard(key)
            pipe.expire(key, self.window_seconds + 1)
            results = pipe.execute()
            count = results[2]
            return count <= limit
        except Exception:
            # Redis unavailable — fall back to in-memory for this request
            return self._memory_check(key, limit)

    def _memory_check(self, key: str, limit: int) -> bool:
        now = time()
        bucket = self._buckets[key]
        while bucket and now - bucket[0] > self.window_seconds:
            bucket.popleft()
        if len(bucket) >= limit:
            return False
        bucket.append(now)
        return True
