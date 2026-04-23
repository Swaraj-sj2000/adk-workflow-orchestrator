import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware

from app.core._config import settings
from app.core._tenant_context import TenantContext
from app.db._database import SessionLocal
from app.models._tenant_settings import TenantSettings

_logger = logging.getLogger(__name__)


class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        tenant_id = None
        role = None
        auth_header = request.headers.get("Authorization", "")

        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1].strip()
            try:
                payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
                tenant_id = payload.get("tenant_id")
                role = payload.get("role")
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
            path = request.url.path or ""
            if role == "platform_owner":
                return await call_next(request)

            if tenant_id is not None and not path.startswith("/auth") and not path.startswith("/owner"):
                db = SessionLocal()
                try:
                    tenant_settings = db.query(TenantSettings).filter(TenantSettings.tenant_id == tenant_id).first()
                finally:
                    db.close()

                if tenant_settings and tenant_settings.suspended:
                    return JSONResponse(
                        status_code=402,
                        content={
                            "detail": "Account suspended. Contact support.",
                            "suspension_reason": tenant_settings.suspension_reason,
                        },
                    )
            return await call_next(request)
        finally:
            TenantContext.clear()
