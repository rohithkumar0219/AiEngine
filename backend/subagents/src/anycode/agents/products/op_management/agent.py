"""OP Management Product Agent implementation."""

from __future__ import annotations

from anycode.agents.products.base_agent import BaseProductAgent
from anycode.agents.products.op_management.manifest import MANIFEST
from anycode.agents.products.op_management.policies import ALLOWED_ROLES
from anycode.agents.products.op_management.tools import (
    book_appointment_tool,
    cancel_appointment_tool,
    check_doctor_availability_tool,
    generate_op_summary_tool,
    issue_token_tool,
)
from anycode.agents.products.op_management.workflows import run_op_workflow
from anycode.agents.products.shared_schemas import AgentRequest, AgentResponse, ProductId


class OPManagementAgent(BaseProductAgent):
    """Product Agent for Iryax OP Management."""

    product_id = ProductId.OP_MANAGEMENT
    name = MANIFEST["name"]
    description = MANIFEST["description"]
    supported_intents = MANIFEST["intents"]
    required_roles = ALLOWED_ROLES

    def __init__(self):
        super().__init__()
        self.register_tool("book_appointment", book_appointment_tool)
        self.register_tool("cancel_appointment", cancel_appointment_tool)
        self.register_tool("issue_token", issue_token_tool)
        self.register_tool("check_doctor_availability", check_doctor_availability_tool)
        self.register_tool("generate_op_summary", generate_op_summary_tool)

    def handle(self, request: AgentRequest) -> AgentResponse:
        status, text, data, tools_used, appr = run_op_workflow(
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
