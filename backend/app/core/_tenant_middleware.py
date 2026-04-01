# backend/app/core/_tenant_middleware.py

"""
ASGI middleware for multi-tenant request handling.
Detects and validates tenant for each request.
"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.core._tenant_context import TenantContext, detect_tenant_from_request, InvalidTenantError
from app.db._database import SessionLocal
from app.models._organization import Organization
import logging

logger = logging.getLogger(__name__)


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Middleware that:
    1. Detects tenant from request
    2. Validates tenant exists
    3. Sets tenant context
    4. Makes organization available to route handlers
    """
    
    def __init__(self, app, skip_paths: list = None):
        super().__init__(app)
        # Paths to skip tenant detection
        self.skip_paths = skip_paths or [
            "/health",
            "/docs",
            "/openapi.json",
            "/redoc",
            "/favicon.ico",
            "/api/v1/auth/login",
            "/api/v1/auth/signup",
            "/api/v1/auth/accept-invite",
        ]
    
    async def dispatch(self, request: Request, call_next):
        """Process request and set tenant context"""
        
        # Skip tenant detection for certain paths
        if self._should_skip(request.url.path):
            TenantContext.set_org_id("seed")  # Default to seed org for public routes
            response = await call_next(request)
            TenantContext.clear()
            return response
        
        try:
            # Extract tenant from request
            headers_dict = dict(request.headers)
            org_id_or_slug = detect_tenant_from_request(
                headers_dict,
                request.url.path
            )
            
            if not org_id_or_slug:
                # No tenant found - could be request to public endpoints
                # For now, default to 'seed' organization
                org_id_or_slug = "seed"
            
            # Validate tenant exists
            db = SessionLocal()
            try:
                # Try to find by ID first, then by slug
                org = db.query(Organization).filter_by(id=org_id_or_slug).first()
                if not org:
                    org = db.query(Organization).filter_by(slug=org_id_or_slug).first()
                
                if not org:
                    logger.warning(f"Organization not found: {org_id_or_slug}")
                    return JSONResponse(
                        status_code=404,
                        content={"detail": f"Organization not found: {org_id_or_slug}"}
                    )
                
                # Set tenant context
                TenantContext.set_org_id(org.id)
                
                # Pass org to request for use in route handlers
                request.state.organization = org
                request.state.org_id = org.id
                
                # Process request
                response = await call_next(request)
                
            finally:
                db.close()
                TenantContext.clear()
            
            return response
            
        except Exception as e:
            logger.error(f"Error in tenant middleware: {e}")
            return JSONResponse(
                status_code=500,
                content={"detail": f"Tenant error: {str(e)}"}
            )
    
    def _should_skip(self, path: str) -> bool:
        """Check if path should skip tenant detection"""
        for skip_path in self.skip_paths:
            if path.startswith(skip_path) or path == skip_path:
                return True
        return False
