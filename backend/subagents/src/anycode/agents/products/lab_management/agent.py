"""Lab Management Product Agent implementation."""

from __future__ import annotations

from anycode.agents.products.base_agent import BaseProductAgent
from anycode.agents.products.lab_management.manifest import MANIFEST
from anycode.agents.products.lab_management.policies import ALLOWED_ROLES
from anycode.agents.products.lab_management.tools import (
    create_lab_order_tool,
    enter_results_tool,
    generate_lab_report_summary_tool,
    register_sample_tool,
    release_result_tool,
)
from anycode.agents.products.lab_management.workflows import run_lab_workflow
from anycode.agents.products.shared_schemas import AgentRequest, AgentResponse, ProductId


class LabManagementAgent(BaseProductAgent):
    """Product Agent for Iryax Lab Management."""

    product_id = ProductId.LAB_MANAGEMENT
    name = MANIFEST["name"]
    description = MANIFEST["description"]
    supported_intents = MANIFEST["intents"]
    required_roles = ALLOWED_ROLES

    def __init__(self):
        super().__init__()
        self.register_tool("create_lab_order", create_lab_order_tool)
        self.register_tool("register_sample", register_sample_tool)
        self.register_tool("enter_results", enter_results_tool)
        self.register_tool("release_result", release_result_tool)
        self.register_tool("lab_report_summary", generate_lab_report_summary_tool)

    def handle(self, request: AgentRequest) -> AgentResponse:
        status, text, data, tools_used, appr = run_lab_workflow(
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
