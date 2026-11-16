"""Task Management Product Agent implementation."""

from __future__ import annotations

from anycode.agents.products.base_agent import BaseProductAgent
from anycode.agents.products.shared_schemas import (
    AgentRequest,
    AgentResponse,
    ProductId,
)
from anycode.agents.products.task_management.manifest import MANIFEST
from anycode.agents.products.task_management.policies import ALLOWED_ROLES
from anycode.agents.products.task_management.tools import (
    create_task_tool,
    decompose_task_tool,
    detect_blockers_tool,
    summarize_project_tool,
)
from anycode.agents.products.task_management.workflows import run_task_workflow


class TaskManagementAgent(BaseProductAgent):
    """Product Agent for Iryax Task Management."""

    product_id = ProductId.TASK_MANAGEMENT
    name = MANIFEST["name"]
    description = MANIFEST["description"]
    supported_intents = MANIFEST["intents"]
    required_roles = ALLOWED_ROLES

    def __init__(self):
        super().__init__()
        self.register_tool("create_task", create_task_tool)
        self.register_tool("decompose_task", decompose_task_tool)
        self.register_tool("detect_blockers", detect_blockers_tool)
        self.register_tool("summarize_project", summarize_project_tool)

    def handle(self, request: AgentRequest) -> AgentResponse:
        status, text, data, tools_used, appr = run_task_workflow(
            request.query, request.parameters, request.context
        )
        return AgentResponse(
            product_id=self.product_id,
            status=status,
            response_text=text,
            structured_data=data,
            tools_executed=tools_used,
            approval_request=appr,
        )
