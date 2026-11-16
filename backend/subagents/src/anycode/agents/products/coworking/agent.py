"""Coworking Space Product Agent implementation."""

from __future__ import annotations

from anycode.agents.products.base_agent import BaseProductAgent
from anycode.agents.products.coworking.manifest import MANIFEST
from anycode.agents.products.coworking.policies import ALLOWED_ROLES
from anycode.agents.products.coworking.tools import (
    book_seat_tool,
    cancel_booking_tool,
    check_seat_availability_tool,
    generate_invoice_tool,
    generate_occupancy_report_tool,
)
from anycode.agents.products.coworking.workflows import run_coworking_workflow
from anycode.agents.products.shared_schemas import AgentRequest, AgentResponse, ProductId


class CoworkingAgent(BaseProductAgent):
    """Product Agent for Iryax Coworking Space."""

    product_id = ProductId.COWORKING
    name = MANIFEST["name"]
    description = MANIFEST["description"]
    supported_intents = MANIFEST["intents"]
    required_roles = ALLOWED_ROLES

    def __init__(self):
        super().__init__()
        self.register_tool("check_seat_availability", check_seat_availability_tool)
        self.register_tool("book_seat", book_seat_tool)
        self.register_tool("cancel_booking", cancel_booking_tool)
        self.register_tool("generate_invoice", generate_invoice_tool)
        self.register_tool("occupancy_report", generate_occupancy_report_tool)

    def handle(self, request: AgentRequest) -> AgentResponse:
        status, text, data, tools_used, appr = run_coworking_workflow(
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
