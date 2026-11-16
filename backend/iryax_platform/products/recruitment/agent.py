"""Recruitment Product Agent."""

from __future__ import annotations

from typing import Any, Dict, List

from iryax_platform.core.context import ProductId, Role
from iryax_platform.core.contracts import (
    AgentRequest,
    AgentResponse,
    ExecutionStatus,
    ToolCallRecord,
)
from iryax_platform.products.base import BaseProductAgent
from iryax_platform.products.recruitment.schemas import CandidateProfile, JobDescription
from iryax_platform.products.recruitment.service import RecruitmentService


class RecruitmentAgent(BaseProductAgent):
    """Product Agent for Iryax Recruitment (ATS, resume parsing, candidate matching, interviews)."""

    product_id = ProductId.RECRUITMENT
    name = "Iryax Recruitment Agent"
    description = (
        "Assists with job postings, resume parsing, candidate matching, "
        "interview scheduling proposals, and recruiter communications."
    )
    supported_intents = [
        "parse_resume",
        "match_candidates",
        "schedule_interview",
        "draft_communication",
        "make_offer",
        "general_recruitment_query",
    ]
    required_roles = [Role.RECRUITER, Role.HR_ADMIN, Role.TENANT_ADMIN]

    def __init__(self, service: RecruitmentService | None = None):
        super().__init__()
        self.service = service or RecruitmentService()
        self._register_default_tools()

    def _register_default_tools(self):
        self.register_tool("parse_resume", self.service.parse_resume)
        self.register_tool("match_candidate", self.service.match_candidate)
        self.register_tool("propose_interview", self.service.propose_interview)
        self.register_tool("draft_communication", self.service.draft_communication)
        self.register_tool("create_hire_offer_approval", self.service.create_hire_offer_approval)

    def handle_request(self, request: AgentRequest) -> AgentResponse:
        query_lower = request.query.lower()
        tools_executed: List[ToolCallRecord] = []

        # 1. Check if user is asking to extend an offer or hire
        if any(w in query_lower for w in ("offer", "hire candidate", "extend offer", "employment contract")):
            cand_name = request.parameters.get("candidate_name", "Applicant")
            job_title = request.parameters.get("job_title", "Software Engineer")
            salary = float(request.parameters.get("offered_salary", 800000.0))

            call_record = self.execute_tool(
                "create_hire_offer_approval",
                {
                    "context": request.context,
                    "candidate_name": cand_name,
                    "job_title": job_title,
                    "offered_salary": salary,
                },
                request.context,
            )
            tools_executed.append(call_record)
            approval_req = call_record.output

            return AgentResponse(
                product_id=self.product_id,
                status=ExecutionStatus.PENDING_APPROVAL,
                response_text=(
                    f"In accordance with hiring governance policies, extending an employment offer "
                    f"to {cand_name} for the position of {job_title} requires authorized human approval. "
                    f"An approval request (ID: {approval_req.approval_id}) has been created for HR/Admin sign-off."
                ),
                structured_data={"approval_id": approval_req.approval_id, "status": "pending_approval"},
                tools_executed=tools_executed,
                approval_request=approval_req,
            )

        # 2. Check if user is asking to parse a resume
        if "resume" in query_lower or "cv" in query_lower or "applicant" in query_lower:
            resume_text = request.parameters.get("resume_text", request.query)
            call_record = self.execute_tool("parse_resume", {"resume_text": resume_text}, request.context)
            tools_executed.append(call_record)
            profile: CandidateProfile = call_record.output

            # If job description is also supplied, score match
            job_info = request.parameters.get("job")
            match_data = None
            if job_info and isinstance(job_info, dict):
                job = JobDescription(**job_info)
                match_call = self.execute_tool(
                    "match_candidate",
                    {"candidate": profile, "job": job},
                    request.context,
                )
                tools_executed.append(match_call)
                match_data = match_call.output.model_dump()

            return AgentResponse(
                product_id=self.product_id,
                status=ExecutionStatus.SUCCESS,
                response_text=(
                    f"Parsed applicant profile for {profile.name} ({profile.email}). "
                    f"Identified {profile.years_experience} years of experience and skills: {', '.join(profile.skills)}."
                ),
                structured_data={
                    "candidate": profile.model_dump(),
                    "match": match_data,
                },
                tools_executed=tools_executed,
            )

        # 3. Check if user is asking to schedule an interview
        if any(w in query_lower for w in ("interview", "schedule", "calendar slot")):
            cand_name = request.parameters.get("candidate_name", "Jane Doe")
            job_id = request.parameters.get("job_id", "job_rec_01")
            time_slot = request.parameters.get("scheduled_time", "Tomorrow at 10:00 AM IST")
            interviewer = request.parameters.get("interviewer", "Lead Recruiter")

            call_record = self.execute_tool(
                "propose_interview",
                {
                    "candidate_name": cand_name,
                    "job_id": job_id,
                    "scheduled_time": time_slot,
                    "interviewer": interviewer,
                },
                request.context,
            )
            tools_executed.append(call_record)
            slot = call_record.output

            return AgentResponse(
                product_id=self.product_id,
                status=ExecutionStatus.SUCCESS,
                response_text=(
                    f"Proposed interview slot for {cand_name} on {time_slot} with {interviewer}. "
                    f"Slot status: {slot.status} (ID: {slot.interview_id})."
                ),
                structured_data=slot.model_dump(),
                tools_executed=tools_executed,
            )

        # 4. Check if live backend is requested for live database sync
        if "sync" in query_lower or "ingrainhire" in query_lower:
            if not self.service.is_backend_connected():
                return AgentResponse(
                    product_id=self.product_id,
                    status=ExecutionStatus.BLOCKED_BACKEND,
                    response_text=(
                        "Live IngrainHire recruitment API integration is not configured in this environment "
                        "(missing INGRAINHIRE_API_URL / INGRAINHIRE_API_KEY). "
                        "Offline resume parsing, matching, and interview workflows remain available."
                    ),
                    backend_supported=False,
                    missing_backend_message="Missing INGRAINHIRE_API_URL and INGRAINHIRE_API_KEY",
                )

        # 5. Default recruitment summary
        return AgentResponse(
            product_id=self.product_id,
            status=ExecutionStatus.SUCCESS,
            response_text=(
                "Iryax Recruitment Agent is active. You can parse candidate resumes, match applicants against "
                "job requirements, propose interview schedule slots, draft candidate communications, or submit "
                "offer proposals for HR approval."
            ),
            tools_executed=[],
        )
