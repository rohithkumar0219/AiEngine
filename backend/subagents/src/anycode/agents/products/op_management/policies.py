"""OP Management policies — RBAC and operation gates."""

from __future__ import annotations

from anycode.agents.products.shared_policies import check_product_authorization
from anycode.agents.products.shared_schemas import ProductId, Role, TenantContext

ALLOWED_ROLES = [
    Role.SUPER_ADMIN,
    Role.TENANT_ADMIN,
    Role.RECEPTIONIST,
    Role.DOCTOR,
    Role.HEALTH_WORKER,
]
SCHEDULE_OVERRIDE_ROLES = [Role.SUPER_ADMIN, Role.TENANT_ADMIN, Role.DOCTOR]


def is_authorized(context: TenantContext) -> bool:
    return check_product_authorization(ProductId.OP_MANAGEMENT, context)


def is_schedule_override(query: str) -> bool:
    """Return True when the query attempts to override a doctor's schedule."""
    q = query.lower()
    return any(
        w in q
        for w in (
            "override schedule",
            "force appointment",
            "reassign doctor",
            "bulk cancel",
            "clear all slots",
        )
    )
