"""Base Product Agent Protocol and Abstract Class."""

from __future__ import annotations

import logging
import time
import uuid
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional

from iryax_platform.core.audit import audit_logger
from iryax_platform.core.context import ProductId, Role, TenantContext
from iryax_platform.core.contracts import (
    AgentRequest,
    AgentResponse,
    AuditEntry,
    ExecutionStatus,
    ToolCallRecord,
)

logger = logging.getLogger(__name__)


class BaseProductAgent(ABC):
    """Abstract base class for all Iryax specialized product agents."""

    product_id: ProductId
    name: str
    description: str
    supported_intents: List[str]
    required_roles: List[Role]

    def __init__(self):
        self._tools: Dict[str, Callable[..., Any]] = {}

    def register_tool(self, name: str, func: Callable[..., Any]) -> None:
        self._tools[name] = func

    def get_tool(self, name: str) -> Optional[Callable[..., Any]]:
        return self._tools.get(name)

    def list_tools(self) -> List[str]:
        return list(self._tools.keys())

    def validate_permissions(self, context: TenantContext) -> bool:
        """Validate whether the user context has permission to interact with this product."""
        return context.is_authorized_for_product(self.product_id)

    def execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        context: TenantContext,
    ) -> ToolCallRecord:
        """Execute a registered tool with timing, logging, and error boundary."""
        tool_fn = self._tools.get(tool_name)
        if not tool_fn:
            raise ValueError(
                f"Tool '{tool_name}' is not registered with agent {self.product_id}"
            )

        start = time.perf_counter()
        try:
            # Inject context if the tool function expects it
            import inspect

            sig = inspect.signature(tool_fn)
            kwargs = dict(arguments)
            if "context" in sig.parameters and "context" not in kwargs:
                kwargs["context"] = context

            result = tool_fn(**kwargs)
            duration_ms = (time.perf_counter() - start) * 1000
            return ToolCallRecord(
                tool_name=tool_name,
                arguments=arguments,
                output=result,
                duration_ms=round(duration_ms, 2),
                status="success",
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.error("Error executing tool '%s': %s", tool_name, e)
            return ToolCallRecord(
                tool_name=tool_name,
                arguments=arguments,
                output={"error": str(e)},
                duration_ms=round(duration_ms, 2),
                status="failed",
            )

    @abstractmethod
    def handle_request(self, request: AgentRequest) -> AgentResponse:
        """Product-specific business logic handling the request."""
        raise NotImplementedError

    def run(self, request: AgentRequest) -> AgentResponse:
        """Orchestrates request execution with permissions, validation, and audit logging."""
        start_time = time.perf_counter()
        audit_id = f"aud_{uuid.uuid4().hex[:12]}"

        # 1. Permission check
        if not self.validate_permissions(request.context):
            resp = AgentResponse(
                product_id=self.product_id,
                status=ExecutionStatus.PERMISSION_DENIED,
                response_text=(
                    f"Access Denied: User '{request.context.user_id}' does not possess "
                    f"the required role for {self.name}. Required roles: {[r.value for r in self.required_roles]}"
                ),
                audit_id=audit_id,
                execution_time_ms=round((time.perf_counter() - start_time) * 1000, 2),
            )
            audit_logger.log(
                AuditEntry(
                    audit_id=audit_id,
                    tenant_id=request.context.tenant_id,
                    user_id=request.context.user_id,
                    roles=request.context.roles,
                    product_id=self.product_id,
                    query=request.query,
                    intent="permission_check",
                    status=ExecutionStatus.PERMISSION_DENIED,
                    tools_used=[],
                )
            )
            return resp

        # 2. Execute business workflow
        try:
            resp = self.handle_request(request)
        except Exception as e:
            logger.exception("Unexpected error in agent %s: %s", self.product_id, e)
            resp = AgentResponse(
                product_id=self.product_id,
                status=ExecutionStatus.FAILED,
                response_text=f"An error occurred while executing the {self.name} workflow: {str(e)}",
                audit_id=audit_id,
                execution_time_ms=round((time.perf_counter() - start_time) * 1000, 2),
            )

        resp.audit_id = audit_id
        resp.execution_time_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # 3. Log audit event
        audit_logger.log(
            AuditEntry(
                audit_id=audit_id,
                tenant_id=request.context.tenant_id,
                user_id=request.context.user_id,
                roles=request.context.roles,
                product_id=self.product_id,
                query=request.query,
                intent=getattr(resp, "intent", self.supported_intents[0] if self.supported_intents else "general"),
                status=resp.status,
                tools_used=[t.tool_name for t in resp.tools_executed],
                has_approval=resp.approval_request is not None,
                approval_id=resp.approval_request.approval_id if resp.approval_request else None,
            )
        )

        return resp
