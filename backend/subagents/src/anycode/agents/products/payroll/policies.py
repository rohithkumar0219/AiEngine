"""Payroll governance policies and payment gates."""

from __future__ import annotations

from anycode.agents.products.shared_policies import check_product_authorization
from anycode.agents.products.shared_schemas import ProductId, Role, TenantContext

ALLOWED_ROLES = [Role.SUPER_ADMIN, Role.TENANT_ADMIN, Role.HR_ADMIN, Role.PAYROLL_ADMIN, Role.EMPLOYEE]
PAYMENT_RELEASE_ROLES = [Role.SUPER_ADMIN, Role.PAYROLL_ADMIN]


def is_authorized(context: TenantContext) -> bool:
    return check_product_authorization(ProductId.PAYROLL, context)


def is_payment_release_request(query: str) -> bool:
    q = query.lower().replace("_", " ")
    return any(w in q for w in ("release payment", "disburse salary", "payout", "send money", "execute payroll"))
