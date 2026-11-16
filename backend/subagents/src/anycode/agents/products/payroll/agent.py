"""Payroll Product Agent implementation."""

from __future__ import annotations

from anycode.agents.products.base_agent import BaseProductAgent
from anycode.agents.products.payroll.manifest import MANIFEST
from anycode.agents.products.payroll.policies import ALLOWED_ROLES
from anycode.agents.products.payroll.tools import (
    calculate_draft_payroll_tool,
    generate_payslip_tool,
    reconcile_attendance_tool,
)
from anycode.agents.products.payroll.workflows import run_payroll_workflow
from anycode.agents.products.shared_schemas import (
    AgentRequest,
    AgentResponse,
    ProductId,
)


class PayrollAgent(BaseProductAgent):
    """Product Agent for Iryax Attendance & Payroll."""

    product_id = ProductId.PAYROLL
    name = MANIFEST["name"]
    description = MANIFEST["description"]
    supported_intents = MANIFEST["intents"]
    required_roles = ALLOWED_ROLES

    def __init__(self):
        super().__init__()
        self.register_tool("reconcile_attendance", reconcile_attendance_tool)
        self.register_tool("calculate_draft_payroll", calculate_draft_payroll_tool)
        self.register_tool("generate_payslip", generate_payslip_tool)

    def handle(self, request: AgentRequest) -> AgentResponse:
        status, text, data, tools_used, appr = run_payroll_workflow(
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
