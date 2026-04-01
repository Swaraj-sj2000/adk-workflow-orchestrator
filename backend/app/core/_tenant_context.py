# backend/app/core/_tenant_context.py

"""
Tenant context management for multi-tenant requests.
Provides middleware and utilities to track which organization a request belongs to.
"""

from contextvars import ContextVar
from typing import Optional, Dict
from datetime import datetime
import uuid

# Context variables for current request
current_org_id: ContextVar[Optional[str]] = ContextVar("current_org_id", default=None)
current_user_id: ContextVar[Optional[str]] = ContextVar("current_user_id", default=None)
current_org_context: ContextVar[Dict] = ContextVar("current_org_context", default={})


class TenantContext:
    """Helper class to manage tenant context"""
    
    @staticmethod
    def set_org_id(org_id: str) -> None:
        """Set the current organization ID"""
        current_org_id.set(org_id)
    
    @staticmethod
    def get_org_id() -> Optional[str]:
        """Get the current organization ID"""
        return current_org_id.get()
    
    @staticmethod
    def set_user_id(user_id: str) -> None:
        """Set the current user ID"""
        current_user_id.set(user_id)
    
    @staticmethod
    def get_user_id() -> Optional[str]:
        """Get the current user ID"""
        return current_user_id.get()
    
    @staticmethod
    def set_context(org_id: str, user_id: Optional[str] = None, **kwargs) -> None:
        """Set full context"""
        current_org_id.set(org_id)
        if user_id:
            current_user_id.set(user_id)
        
        context = {
            "org_id": org_id,
            "user_id": user_id,
            "timestamp": datetime.utcnow(),
            **kwargs
        }
        current_org_context.set(context)
    
    @staticmethod
    def get_context() -> Dict:
        """Get full context"""
        return current_org_context.get()
    
    @staticmethod
    def clear() -> None:
        """Clear all context"""
        current_org_id.set(None)
        current_user_id.set(None)
        current_org_context.set({})


class InvalidTenantError(Exception):
    """Raised when tenant cannot be determined or is invalid"""
    pass


def extract_org_from_subdomain(host: str) -> Optional[str]:
    """
    Extract organization slug from subdomain.
    Examples:
        - acme.localhost:8000 → acme
        - admin.example.com → admin
        - example.com → None
    """
    if not host:
        return None
    
    # Remove port
    host = host.split(":")[0]
    
    # Split by dots
    parts = host.split(".")
    
    # If more than 2 parts, first part is subdomain
    if len(parts) > 2:
        return parts[0]
    
    # For localhost with subdomain
    if "localhost" in host and len(parts) >= 2:
        return parts[0]
    
    return None


def extract_org_from_url_path(path: str) -> Optional[str]:
    """
    Extract organization from URL path.
    Example:
        - /api/v1/orgs/acme-corp/projects → acme-corp
    """
    parts = path.split("/")
    if len(parts) > 3 and parts[1] == "api" and parts[3] == "orgs":
        return parts[4]
    return None


def extract_org_from_headers(headers: dict) -> Optional[str]:
    """Extract organization from custom headers"""
    # Check for X-Organization-ID header
    org_id = headers.get("X-Organization-ID")
    if org_id:
        return org_id
    
    # Check for X-Organization-Slug header
    org_slug = headers.get("X-Organization-Slug")
    if org_slug:
        return org_slug
    
    return None


def detect_tenant_from_request(request_headers: dict, request_path: str) -> Optional[str]:
    """
    Detect tenant from request using multiple strategies.
    Tries in order:
        1. Custom headers (X-Organization-ID, X-Organization-Slug)
        2. URL path (/api/v1/orgs/{org}/...)
        3. Subdomain (acme.example.com)
    """
    # Strategy 1: Headers
    org_id = extract_org_from_headers(request_headers)
    if org_id:
        return org_id
    
    # Strategy 2: URL path
    org_id = extract_org_from_url_path(request_path)
    if org_id:
        return org_id
    
    # Strategy 3: Subdomain
    host = request_headers.get("Host")
    org_slug = extract_org_from_subdomain(host)
    if org_slug:
        return org_slug
    
    return None
