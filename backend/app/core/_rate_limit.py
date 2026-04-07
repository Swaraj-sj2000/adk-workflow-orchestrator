from collections import defaultdict, deque
from time import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, requests_per_window: int = 120, window_seconds: int = 60):
        super().__init__(app)
        self.requests_per_window = requests_per_window
        self.window_seconds = window_seconds
        self._buckets = defaultdict(deque)
        self._skip_prefixes = ("/docs", "/redoc", "/openapi.json", "/")

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self._skip_prefixes and request.method == "GET":
            return await call_next(request)

        now = time()
        client_host = request.client.host if request.client else "unknown"
        path_key = "auth" if request.url.path.startswith("/auth") or request.url.path.startswith("/accept-invite") else request.url.path
        key = f"{client_host}:{path_key}"
        bucket = self._buckets[key]

        while bucket and now - bucket[0] > self.window_seconds:
            bucket.popleft()

        limit = min(self.requests_per_window, 30) if path_key == "auth" else self.requests_per_window
        if len(bucket) >= limit:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please retry shortly."},
            )

        bucket.append(now)
        return await call_next(request)
