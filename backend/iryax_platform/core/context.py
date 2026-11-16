"""Tenant Context, Identity, and Access Control for Multi-Product Agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Sequence
from pydantic import BaseModel, Field


class Role(str, Enum):
    # Global roles
    SUPER_ADMIN = "super_admin"
    TENANT_ADMIN = "tenant_admin"
    AUDITOR = "auditor"

    # Product-specific roles
    RECRUITER = "recruiter"
    HR_ADMIN = "hr_admin"
    PAYROLL_ADMIN = "payroll_admin"
    TASK_LEAD = "task_lead"
    EMPLOYEE = "employee"
    CAMP_COORDINATOR = "camp_coordinator"
    HEALTH_WORKER = "health_worker"
    RECEPTIONIST = "receptionist"
    DOCTOR = "doctor"
    WORKSPACE_ADMIN = "workspace_admin"
    COWORKING_MEMBER = "coworking_member"
    LAB_TECHNICIAN = "lab_technician"
    PATHOLOGIST = "pathologist"
    GUEST = "guest"


class ProductId(str, Enum):
    RECRUITMENT = "iryax.recruitment"
    ATTENDANCE_PAYROLL = "iryax.attendance_payroll"
    TASK_MANAGEMENT = "iryax.task_management"
    MEDICAL_CAMPS = "iryax.medical_camps"
    OP_MANAGEMENT = "iryax.op_management"
    COWORKING_SPACE = "iryax.coworking_space"
    LAB_MANAGEMENT = "iryax.lab_management"


# Product to allowed roles mapping
PRODUCT_ROLE_PERMISSIONS: dict[ProductId, set[Role]] = {
    ProductId.RECRUITMENT: {
        Role.SUPER_ADMIN,
        Role.TENANT_ADMIN,
        Role.RECRUITER,
        Role.HR_ADMIN,
    },
    ProductId.ATTENDANCE_PAYROLL: {
        Role.SUPER_ADMIN,
        Role.TENANT_ADMIN,
        Role.HR_ADMIN,
        Role.PAYROLL_ADMIN,
        Role.EMPLOYEE,  # Can view own payslips/attendance
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
    ProductId.COWORKING_SPACE: {
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

# Operations requiring human-in-the-loop authorization
RESTRICTED_OPERATIONS: dict[str, set[Role]] = {
    "release_payment": {Role.SUPER_ADMIN, Role.PAYROLL_ADMIN},
    "modify_salary_structure": {Role.SUPER_ADMIN, Role.HR_ADMIN},
    "extend_employment_offer": {Role.SUPER_ADMIN, Role.TENANT_ADMIN, Role.HR_ADMIN},
    "clinical_diagnosis": set(),  # NEVER permitted autonomously
    "prescribe_medication": set(),  # NEVER permitted autonomously
    "release_lab_results": {Role.SUPER_ADMIN, Role.PATHOLOGIST},
    "delete_bulk_tasks": {Role.SUPER_ADMIN, Role.TENANT_ADMIN},
    "grant_access_level": {Role.SUPER_ADMIN, Role.WORKSPACE_ADMIN},
    "issue_refund": {Role.SUPER_ADMIN, Role.TENANT_ADMIN, Role.WORKSPACE_ADMIN},
}


class TenantContext(BaseModel):
    """Secure Tenant isolation context enforced across all product agent operations."""

    tenant_id: str = Field(..., description="Unique tenant organization ID")
    user_id: str = Field(..., description="Authenticated user ID")
    roles: list[Role] = Field(default_factory=lambda: [Role.GUEST])
    metadata: dict[str, Any] = Field(default_factory=dict)

    def has_role(self, role: Role) -> bool:
        return Role.SUPER_ADMIN in self.roles or role in self.roles

    def has_any_role(self, roles: Sequence[Role]) -> bool:
        if Role.SUPER_ADMIN in self.roles:
            return True
        return any(r in self.roles for r in roles)

    def is_authorized_for_product(self, product_id: ProductId) -> bool:
        allowed = PRODUCT_ROLE_PERMISSIONS.get(product_id, set())
        return self.has_any_role(list(allowed))

    def is_authorized_for_restricted_op(self, op_name: str) -> bool:
        allowed = RESTRICTED_OPERATIONS.get(op_name, set())
        if not allowed:
            return False
        return self.has_any_role(list(allowed))
