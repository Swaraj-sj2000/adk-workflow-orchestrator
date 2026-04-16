import logging

from fastapi import Request
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware

from app.core._config import settings
from app.core._tenant_context import TenantContext

_logger = logging.getLogger(__name__)


class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        tenant_id = None
        auth_header = request.headers.get("Authorization", "")

        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1].strip()
            try:
                payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
                tenant_id = payload.get("tenant_id")
            except JWTError as exc:
                # Log as a security event so invalid/forged tokens are visible
                _logger.warning(
                    "JWT decode failed on %s %s — possible forged or expired token: %s",
                    request.method,
                    request.url.path,
                    exc,
                )
                tenant_id = None

        # Removed: X-Tenant-ID header fallback.
        # Tenant context must come exclusively from a validated JWT to prevent
        # unauthenticated callers from spoofing their tenant identity.

        request.state.tenant_id = tenant_id
        TenantContext.set_tenant_id(tenant_id)
        try:
            return await call_next(request)
        finally:
            TenantContext.clear()
