"""Lab Management policies — RBAC and operation gates."""

from __future__ import annotations

from anycode.agents.products.shared_policies import check_product_authorization
from anycode.agents.products.shared_schemas import ProductId, Role, TenantContext

ALLOWED_ROLES = [
    Role.SUPER_ADMIN,
    Role.TENANT_ADMIN,
    Role.DOCTOR,
    Role.LAB_TECHNICIAN,
    Role.PATHOLOGIST,
]
RESULT_RELEASE_ROLES = [Role.SUPER_ADMIN, Role.TENANT_ADMIN, Role.PATHOLOGIST]


def is_authorized(context: TenantContext) -> bool:
    return check_product_authorization(ProductId.LAB_MANAGEMENT, context)


def is_result_release_operation(query: str) -> bool:
    """Return True when the query attempts to release or publish lab results."""
    q = query.lower().replace("_", " ")
    return any(
        w in q
        for w in (
            "release result",
            "release report",
            "publish result",
            "finalise report",
            "finalize report",
            "send report",
            "dispatch report",
            "bulk release",
        )
    )
