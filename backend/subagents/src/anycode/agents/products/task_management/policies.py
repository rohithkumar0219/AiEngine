"""Task management policies and bulk operation gates."""

from __future__ import annotations

from anycode.agents.products.shared_policies import check_product_authorization
from anycode.agents.products.shared_schemas import ProductId, Role, TenantContext

ALLOWED_ROLES = [Role.SUPER_ADMIN, Role.TENANT_ADMIN, Role.TASK_LEAD, Role.EMPLOYEE]
BULK_CHANGE_ROLES = [Role.SUPER_ADMIN, Role.TENANT_ADMIN, Role.TASK_LEAD]


def is_authorized(context: TenantContext) -> bool:
    return check_product_authorization(ProductId.TASK_MANAGEMENT, context)


def is_bulk_or_destructive_request(query: str) -> bool:
    q = query.lower()
    return any(w in q for w in ("bulk delete", "delete all", "purge tasks", "mass update", "bulk complete"))
