"""Coworking Space policies — RBAC and operation gates."""

from __future__ import annotations

from anycode.agents.products.shared_policies import check_product_authorization
from anycode.agents.products.shared_schemas import ProductId, Role, TenantContext

ALLOWED_ROLES = [
    Role.SUPER_ADMIN,
    Role.TENANT_ADMIN,
    Role.WORKSPACE_ADMIN,
    Role.COWORKING_MEMBER,
]
REFUND_APPROVAL_ROLES = [Role.SUPER_ADMIN, Role.TENANT_ADMIN, Role.WORKSPACE_ADMIN]


def is_authorized(context: TenantContext) -> bool:
    return check_product_authorization(ProductId.COWORKING, context)


def is_refund_or_high_value_operation(query: str) -> bool:
    """Return True when the query triggers a refund or high-value financial action."""
    q = query.lower()
    return any(
        w in q
        for w in (
            "refund",
            "waive payment",
            "bulk cancel booking",
            "credit override",
            "invoice adjustment",
        )
    )
