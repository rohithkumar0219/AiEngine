"""Recruitment governance and authorization policies."""

from __future__ import annotations

from anycode.agents.products.shared_policies import check_product_authorization
from anycode.agents.products.shared_schemas import ProductId, Role, TenantContext

ALLOWED_ROLES = [Role.SUPER_ADMIN, Role.TENANT_ADMIN, Role.RECRUITER, Role.HR_ADMIN]
OFFER_APPROVAL_ROLES = [Role.SUPER_ADMIN, Role.TENANT_ADMIN, Role.HR_ADMIN]


def is_authorized(context: TenantContext) -> bool:
    return check_product_authorization(ProductId.RECRUITMENT, context)


def is_offer_request(query: str) -> bool:
    q = query.lower()
    return any(w in q for w in ("offer", "hire candidate", "extend offer", "employment contract"))
