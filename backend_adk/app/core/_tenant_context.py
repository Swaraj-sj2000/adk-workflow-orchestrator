from contextvars import ContextVar
from typing import Optional


current_tenant_id: ContextVar[Optional[int]] = ContextVar("current_tenant_id", default=None)


class TenantContext:
    @staticmethod
    def set_tenant_id(tenant_id: Optional[int]) -> None:
        current_tenant_id.set(tenant_id)

    @staticmethod
    def get_tenant_id() -> Optional[int]:
        return current_tenant_id.get()

    @staticmethod
    def clear() -> None:
        current_tenant_id.set(None)
