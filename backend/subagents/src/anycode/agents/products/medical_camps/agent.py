"""Medical Camps Product Agent implementation."""

from __future__ import annotations

from anycode.agents.products.base_agent import BaseProductAgent
from anycode.agents.products.medical_camps.manifest import MANIFEST
from anycode.agents.products.medical_camps.policies import ALLOWED_ROLES
from anycode.agents.products.medical_camps.tools import (
    add_volunteer_tool,
    create_camp_tool,
    generate_camp_summary_tool,
    register_patient_tool,
    validate_vitals_tool,
)
from anycode.agents.products.medical_camps.workflows import run_camp_workflow
from anycode.agents.products.shared_schemas import AgentRequest, AgentResponse, ProductId


class MedicalCampsAgent(BaseProductAgent):
    """Product Agent for Iryax Medical Camps."""

    product_id = ProductId.MEDICAL_CAMPS
    name = MANIFEST["name"]
    description = MANIFEST["description"]
    supported_intents = MANIFEST["intents"]
    required_roles = ALLOWED_ROLES

    def __init__(self):
        super().__init__()
        self.register_tool("create_camp", create_camp_tool)
        self.register_tool("register_patient", register_patient_tool)
        self.register_tool("validate_vitals", validate_vitals_tool)
        self.register_tool("add_volunteer", add_volunteer_tool)
        self.register_tool("generate_camp_summary", generate_camp_summary_tool)

    def handle(self, request: AgentRequest) -> AgentResponse:
        status, text, data, tools_used, appr = run_camp_workflow(
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
