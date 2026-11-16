"""Shared schemas and data models for all Iryax product agents."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class Role(str, Enum):
    """Platform roles for multi-product RBAC."""
    SUPER_ADMIN = "super_admin"
    TENANT_ADMIN = "tenant_admin"
    AUDITOR = "auditor"
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
    """Registered unique identifiers for Iryax's 7 core products."""
    RECRUITMENT = "iryax.recruitment"
    PAYROLL = "iryax.payroll"
    TASK_MANAGEMENT = "iryax.task_management"
    MEDICAL_CAMPS = "iryax.medical_camps"
    OP_MANAGEMENT = "iryax.op_management"
    COWORKING = "iryax.coworking"
    LAB_MANAGEMENT = "iryax.lab_management"


class ExecutionStatus(str, Enum):
    """Execution status for agent workflows."""
    SUCCESS = "success"
    PENDING_APPROVAL = "pending_approval"
    BLOCKED_BACKEND = "blocked_by_missing_backend"
    AMBIGUOUS = "ambiguous_clarification_required"
    PERMISSION_DENIED = "permission_denied"
    FAILED = "failed"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class TenantContext(BaseModel):
    """Tenant isolation context enforced across all product agents."""
    tenant_id: str = Field(..., description="Organization / tenant identifier")
    user_id: str = Field(..., description="Caller user ID")
    roles: List[Role] = Field(default_factory=lambda: [Role.GUEST])
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def has_role(self, role: Role) -> bool:
        return Role.SUPER_ADMIN in self.roles or role in self.roles

    def has_any_role(self, roles: List[Role]) -> bool:
        if Role.SUPER_ADMIN in self.roles:
            return True
        return any(r in self.roles for r in roles)


class ToolCallRecord(BaseModel):
    """Audit record of a tool call."""
    tool_name: str
    arguments: Dict[str, Any]
    output: Any
    duration_ms: float = 0.0
    status: str = "success"


class ApprovalRequest(BaseModel):
    """Human-in-the-loop approval request for restricted actions."""
    approval_id: str
    tenant_id: str
    product_id: ProductId
    operation_name: str
    payload: Dict[str, Any]
    required_roles: List[Role]
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    decided_by: Optional[str] = None
    decided_at: Optional[str] = None
    rejection_reason: Optional[str] = None


class AgentRequest(BaseModel):
    """Incoming request to an agent."""
    query: str
    context: TenantContext
    product_hint: Optional[ProductId] = None
    idempotency_key: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)


class AgentResponse(BaseModel):
    """Structured response from an agent."""
    product_id: ProductId
    status: ExecutionStatus
    response_text: str
    structured_data: Optional[Dict[str, Any]] = None
    tools_executed: List[ToolCallRecord] = Field(default_factory=list)
    clarifying_question: Optional[str] = None
    approval_request: Optional[ApprovalRequest] = None
    audit_id: Optional[str] = None
    backend_supported: bool = True
    missing_backend_message: Optional[str] = None
    execution_time_ms: float = 0.0
