"""Medical Camps policies — RBAC and operation gates."""

from __future__ import annotations

from anycode.agents.products.shared_policies import check_product_authorization
from anycode.agents.products.shared_schemas import ProductId, Role, TenantContext

ALLOWED_ROLES = [
    Role.SUPER_ADMIN,
    Role.TENANT_ADMIN,
    Role.CAMP_COORDINATOR,
    Role.HEALTH_WORKER,
    Role.DOCTOR,
]
RESULT_RELEASE_ROLES = [Role.SUPER_ADMIN, Role.TENANT_ADMIN, Role.DOCTOR]


def is_authorized(context: TenantContext) -> bool:
    return check_product_authorization(ProductId.MEDICAL_CAMPS, context)


def is_sensitive_health_operation(query: str) -> bool:
    """Return True when the query involves releasing patient health data."""
    q = query.lower()
    return any(
        w in q
        for w in (
            "release result",
            "publish report",
            "share diagnosis",
            "export patient",
            "bulk export",
            "patient data dump",
        )
    )
