"""Base Product Agent contract and foundation."""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional

from anycode.agents.products.shared_policies import check_product_authorization
from anycode.agents.products.shared_schemas import (
    AgentRequest,
    AgentResponse,
    ExecutionStatus,
    ProductId,
    Role,
    TenantContext,
    ToolCallRecord,
)
from anycode.agents.products.shared_services import audit_service, idempotency_service

logger = logging.getLogger(__name__)


class BaseProductAgent(ABC):
    """Abstract base class for all 7 Iryax specialized product agents."""

    product_id: ProductId
    name: str
    description: str
    supported_intents: List[str]
    required_roles: List[Role]

    def __init__(self):
        self._tools: Dict[str, Callable[..., Any]] = {}

    def register_tool(self, name: str, fn: Callable[..., Any]) -> None:
        self._tools[name] = fn

    def list_tools(self) -> List[str]:
        return list(self._tools.keys())

    def invoke_tool(self, name: str, arguments: Dict[str, Any]) -> ToolCallRecord:
        fn = self._tools.get(name)
        if not fn:
            raise ValueError(f"Tool '{name}' is not registered with {self.name}")

        t0 = time.perf_counter()
        try:
            out = fn(**arguments)
            duration = round((time.perf_counter() - t0) * 1000, 2)
            return ToolCallRecord(tool_name=name, arguments=arguments, output=out, duration_ms=duration, status="success")
        except Exception as e:
            duration = round((time.perf_counter() - t0) * 1000, 2)
            logger.error("Error executing tool %s: %s", name, e)
            return ToolCallRecord(tool_name=name, arguments=arguments, output={"error": str(e)}, duration_ms=duration, status="failed")

    @abstractmethod
    def handle(self, request: AgentRequest) -> AgentResponse:
        """Core product business logic."""
        raise NotImplementedError

    def execute(self, request: AgentRequest) -> AgentResponse:
        """Public execution entry point with RBAC, idempotency, timing, and audit."""
        start_time = time.perf_counter()

        # 1. Idempotency check
        if request.idempotency_key:
            cached = idempotency_service.get(request.context.tenant_id, request.idempotency_key)
            if cached:
                return cached

        # 2. RBAC check
        if not check_product_authorization(self.product_id, request.context):
            resp = AgentResponse(
                product_id=self.product_id,
                status=ExecutionStatus.PERMISSION_DENIED,
                response_text=(
                    f"Access Denied: User '{request.context.user_id}' lacks required role for {self.name}. "
                    f"Required: {[r.value for r in self.required_roles]}"
                ),
                execution_time_ms=round((time.perf_counter() - start_time) * 1000, 2),
            )
            audit_service.record(
                request.context.tenant_id,
                request.context.user_id,
                self.product_id,
                "access_check",
                ExecutionStatus.PERMISSION_DENIED.value,
            )
            return resp

        # 3. Handle request
        try:
            resp = self.handle(request)
        except Exception as e:
            logger.exception("Error executing product agent %s: %s", self.product_id, e)
            resp = AgentResponse(
                product_id=self.product_id,
                status=ExecutionStatus.FAILED,
                response_text=f"Execution error in {self.name}: {str(e)}",
                execution_time_ms=round((time.perf_counter() - start_time) * 1000, 2),
            )

        resp.execution_time_ms = round((time.perf_counter() - start_time) * 1000, 2)
        resp.audit_id = audit_service.record(
            request.context.tenant_id,
            request.context.user_id,
            self.product_id,
            request.query[:50],
            resp.status.value,
            {"tools": [t.tool_name for t in resp.tools_executed]},
        )

        if request.idempotency_key and resp.status == ExecutionStatus.SUCCESS:
            idempotency_service.put(request.context.tenant_id, request.idempotency_key, resp)

        return resp
