"""Recruitment Product Agent implementation."""

from __future__ import annotations

from anycode.agents.products.base_agent import BaseProductAgent
from anycode.agents.products.recruitment.manifest import MANIFEST
from anycode.agents.products.recruitment.policies import ALLOWED_ROLES
from anycode.agents.products.recruitment.tools import (
    draft_candidate_email_tool,
    match_candidate_tool,
    parse_resume_tool,
    schedule_interview_tool,
)
from anycode.agents.products.recruitment.workflows import run_recruitment_workflow
from anycode.agents.products.shared_schemas import (
    AgentRequest,
    AgentResponse,
    ProductId,
)


class RecruitmentAgent(BaseProductAgent):
    """Product Agent for Iryax Recruitment."""

    product_id = ProductId.RECRUITMENT
    name = MANIFEST["name"]
    description = MANIFEST["description"]
    supported_intents = MANIFEST["intents"]
    required_roles = ALLOWED_ROLES

    def __init__(self):
        super().__init__()
        self.register_tool("parse_resume", parse_resume_tool)
        self.register_tool("match_candidate", match_candidate_tool)
        self.register_tool("schedule_interview", schedule_interview_tool)
        self.register_tool("draft_candidate_email", draft_candidate_email_tool)

    def handle(self, request: AgentRequest) -> AgentResponse:
        status, text, data, tools_used, appr = run_recruitment_workflow(
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
