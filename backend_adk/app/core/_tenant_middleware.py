from fastapi import Request
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware

from app.core._config import settings
from app.core._tenant_context import TenantContext


class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        tenant_id = None
        auth_header = request.headers.get("Authorization", "")

        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1].strip()
            try:
                payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
                tenant_id = payload.get("tenant_id")
            except JWTError:
                tenant_id = None

        if tenant_id is None:
            header_tenant = request.headers.get("X-Tenant-ID")
            if header_tenant and header_tenant.isdigit():
                tenant_id = int(header_tenant)

        request.state.tenant_id = tenant_id
        TenantContext.set_tenant_id(tenant_id)
        try:
            return await call_next(request)
        finally:
            TenantContext.clear()
