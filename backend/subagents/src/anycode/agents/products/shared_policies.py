"""Shared security policies, RBAC matrices, and governance guardrails."""

from __future__ import annotations

import re
from typing import Dict, List, Set
from anycode.agents.products.shared_schemas import ProductId, Role, TenantContext

PRODUCT_ROLE_PERMISSIONS: Dict[ProductId, Set[Role]] = {
    ProductId.RECRUITMENT: {
        Role.SUPER_ADMIN,
        Role.TENANT_ADMIN,
        Role.RECRUITER,
        Role.HR_ADMIN,
    },
    ProductId.PAYROLL: {
        Role.SUPER_ADMIN,
        Role.TENANT_ADMIN,
        Role.HR_ADMIN,
        Role.PAYROLL_ADMIN,
        Role.EMPLOYEE,
    },
    ProductId.TASK_MANAGEMENT: {
        Role.SUPER_ADMIN,
        Role.TENANT_ADMIN,
        Role.TASK_LEAD,
        Role.EMPLOYEE,
    },
    ProductId.MEDICAL_CAMPS: {
        Role.SUPER_ADMIN,
        Role.TENANT_ADMIN,
        Role.CAMP_COORDINATOR,
        Role.HEALTH_WORKER,
        Role.DOCTOR,
    },
    ProductId.OP_MANAGEMENT: {
        Role.SUPER_ADMIN,
        Role.TENANT_ADMIN,
        Role.RECEPTIONIST,
        Role.DOCTOR,
    },
    ProductId.COWORKING: {
        Role.SUPER_ADMIN,
        Role.TENANT_ADMIN,
        Role.WORKSPACE_ADMIN,
        Role.COWORKING_MEMBER,
    },
    ProductId.LAB_MANAGEMENT: {
        Role.SUPER_ADMIN,
        Role.TENANT_ADMIN,
        Role.LAB_TECHNICIAN,
        Role.PATHOLOGIST,
        Role.DOCTOR,
    },
}

RESTRICTED_OPERATIONS: Dict[str, Set[Role]] = {
    "release_payment": {Role.SUPER_ADMIN, Role.PAYROLL_ADMIN},
    "extend_employment_offer": {Role.SUPER_ADMIN, Role.TENANT_ADMIN, Role.HR_ADMIN},
    "release_lab_results": {Role.SUPER_ADMIN, Role.PATHOLOGIST},
    "delete_bulk_tasks": {Role.SUPER_ADMIN, Role.TENANT_ADMIN, Role.TASK_LEAD},
    "issue_refund": {Role.SUPER_ADMIN, Role.TENANT_ADMIN, Role.WORKSPACE_ADMIN},
}


def check_product_authorization(product_id: ProductId, context: TenantContext) -> bool:
    """Validate whether user context is authorized for product."""
    allowed = PRODUCT_ROLE_PERMISSIONS.get(product_id, set())
    return context.has_any_role(list(allowed))


def check_operation_authorization(operation_name: str, context: TenantContext) -> bool:
    """Validate whether user context is authorized for restricted operation."""
    allowed = RESTRICTED_OPERATIONS.get(operation_name, set())
    if not allowed:
        return False
    return context.has_any_role(list(allowed))


def mask_sensitive_pii(text: str) -> str:
    """Redact emails and phone numbers from public/shared outputs."""
    masked = re.sub(r"[\w\.-]+@[\w\.-]+\.\w+", "[EMAIL REDACTED]", text)
    masked = re.sub(r"\+?\d[\d -]{8,12}\d", "[PHONE REDACTED]", masked)
    return masked
