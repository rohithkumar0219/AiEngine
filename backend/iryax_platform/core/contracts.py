"""Contracts and Typed Schemas for Multi-Product Agents."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from iryax_platform.core.context import ProductId, Role, TenantContext


class ExecutionStatus(str, Enum):
    SUCCESS = "success"
    PENDING_APPROVAL = "pending_approval"
    BLOCKED_BACKEND = "blocked_by_missing_backend"
    AMBIGUOUS = "ambiguous_clarification_required"
    PERMISSION_DENIED = "permission_denied"
    FAILED = "failed"


class ToolCallRecord(BaseModel):
    tool_name: str
    arguments: Dict[str, Any]
    output: Any
    duration_ms: float = 0.0
    status: str = "success"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ApprovalRequest(BaseModel):
    """Represents a sensitive operation queued for explicit human review."""

    approval_id: str
    tenant_id: str
    product_id: ProductId
    operation_name: str
    payload: Dict[str, Any]
    required_roles: List[Role]
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    decided_by: Optional[str] = None
    decided_at: Optional[str] = None
    rejection_reason: Optional[str] = None


class AgentRequest(BaseModel):
    """Typed incoming request dispatched to the multi-product orchestrator."""

    query: str = Field(..., description="User query or command")
    context: TenantContext = Field(..., description="Authenticated tenant & user context")
    product_hint: Optional[ProductId] = Field(
        default=None, description="Optional user/client hint for product"
    )
    idempotency_key: Optional[str] = Field(
        default=None, description="Optional idempotency key to prevent double actions"
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="Structured parameters for execution"
    )


class AgentResponse(BaseModel):
    """Typed execution result returned by the multi-product orchestrator."""

    product_id: Optional[ProductId] = None
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


class AuditEntry(BaseModel):
    """Immutable audit record logged for governance, compliance and tracking."""

    audit_id: str
    tenant_id: str
    user_id: str
    roles: List[Role]
    product_id: Optional[ProductId]
    query: str
    intent: str
    status: ExecutionStatus
    tools_used: List[str]
    has_approval: bool = False
    approval_id: Optional[str] = None
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)
