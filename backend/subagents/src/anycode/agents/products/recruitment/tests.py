
"""Unit and regression tests for the Iryax Recruitment Product Agent.

Covers:
- Agent registration and tool availability
- Role-based access control
- Resume parsing and extracted candidate data
- Candidate-to-job matching
- Human-in-the-loop approval for employment offers
"""

from __future__ import annotations

import pytest

from anycode.agents.products.recruitment.agent import RecruitmentAgent
from anycode.agents.products.recruitment.schemas import (
    CandidateProfile,
    JobPosting,
)
from anycode.agents.products.recruitment.tools import (
    match_candidate_tool,
    parse_resume_tool,
)
from anycode.agents.products.shared_schemas import (
    AgentRequest,
    ApprovalStatus,
    ExecutionStatus,
    ProductId,
    Role,
    TenantContext,
)


# ---------------------------------------------------------------------
# FIXTURES
# ---------------------------------------------------------------------

@pytest.fixture
def recruiter_context() -> TenantContext:
    """Authorized recruitment user."""
    return TenantContext(
        tenant_id="tenant_rec_01",
        user_id="user_rec_01",
        roles=[Role.RECRUITER],
    )


@pytest.fixture
def guest_context() -> TenantContext:
    """Unauthorized guest user."""
    return TenantContext(
        tenant_id="tenant_rec_01",
        user_id="user_guest_01",
        roles=[Role.GUEST],
    )


@pytest.fixture
def hr_context() -> TenantContext:
    """Authorized HR administrator."""
    return TenantContext(
        tenant_id="tenant_rec_01",
        user_id="user_hr_01",
        roles=[Role.HR_ADMIN],
    )


@pytest.fixture
def agent() -> RecruitmentAgent:
    """Create a fresh recruitment agent."""
    return RecruitmentAgent()


@pytest.fixture
def sample_resume() -> str:
    """Sample candidate resume."""
    return (
        "Jane Doe\n"
        "jane.doe@techcorp.com\n"
        "5 years of experience in Python, FastAPI, "
        "React, Docker and SQL."
    )


@pytest.fixture
def sample_candidate() -> CandidateProfile:
    """Sample candidate profile."""
    return CandidateProfile(
        candidate_id="candidate_test_001",
        name="Alex Smith",
        email="alex@domain.com",
        years_experience=4.0,
        skills=["python", "fastapi", "react"],
    )


@pytest.fixture
def sample_job() -> JobPosting:
    """Sample job posting."""
    return JobPosting(
        job_id="job_test_001",
        title="Full Stack Engineer",
        department="Engineering",
        required_skills=[
            "python",
            "fastapi",
            "react",
            "docker",
        ],
        min_years_experience=3.0,
    )


# ---------------------------------------------------------------------
# 1. AGENT INITIALIZATION
# ---------------------------------------------------------------------

def test_recruitment_agent_attributes(agent):
    """Verify recruitment agent identity and registered tools."""

    assert agent.product_id == ProductId.RECRUITMENT

    registered_tools = agent.list_tools()

    assert "parse_resume" in registered_tools
    assert "match_candidate" in registered_tools
    assert "schedule_interview" in registered_tools
    assert "draft_candidate_email" in registered_tools

    assert len(registered_tools) == 4


# ---------------------------------------------------------------------
# 2. ROLE-BASED ACCESS CONTROL
# ---------------------------------------------------------------------

def test_recruitment_agent_rbac_denied(agent, guest_context):
    """Guest users must not access recruitment operations."""

    request = AgentRequest(
        query="parse this resume",
        context=guest_context,
        parameters={
            "resume_text": "Jane Doe jane@example.com"
        },
    )

    response = agent.execute(request)

    assert response.status == ExecutionStatus.PERMISSION_DENIED
    assert "Access Denied" in response.response_text

    assert response.audit_id is None or isinstance(
        response.audit_id, str
    )


def test_recruitment_agent_allows_authorized_recruiter(
    agent,
    recruiter_context,
):
    """Authorized recruiters should pass the RBAC gate."""

    request = AgentRequest(
        query="show recruitment pipeline",
        context=recruiter_context,
    )

    response = agent.execute(request)

    assert response.status == ExecutionStatus.SUCCESS
    assert response.audit_id is not None


# ---------------------------------------------------------------------
# 3. RESUME PARSING
# ---------------------------------------------------------------------

def test_resume_parsing(agent, recruiter_context, sample_resume):
    """Verify resume extraction through the complete agent workflow."""

    request = AgentRequest(
        query="parse candidate resume",
        context=recruiter_context,
        parameters={
            "resume_text": sample_resume,
        },
    )

    response = agent.execute(request)

    assert response.status == ExecutionStatus.SUCCESS

    assert "Jane Doe" in response.response_text
    assert "jane.doe@techcorp.com" in response.response_text

    # The current workflow returns candidate fields directly,
    # not inside a nested 'candidate' dictionary.
    data = response.structured_data

    assert data is not None
    assert data["name"] == "Jane Doe"
    assert data["email"] == "jane.doe@techcorp.com"

    assert data["years_experience"] == 5.0
    assert "python" in data["skills"]
    assert "fastapi" in data["skills"]
    assert "docker" in data["skills"]

    assert data["current_stage"] == "Screened"

    assert data["duplicate_check"] in (
        "Passed (No duplicate record found)",
        "Duplicate Detected",
    )

    assert any(
        tool.tool_name == "parse_resume_tool"
        for tool in response.tools_executed
    )


def test_resume_parsing_direct_tool(sample_resume):
    """Verify the resume parsing service independently."""

    profile = parse_resume_tool(sample_resume)

    assert profile.name == "Jane Doe"
    assert profile.email == "jane.doe@techcorp.com"

    assert profile.years_experience == 5.0
    assert "python" in profile.skills
    assert profile.candidate_id.startswith("cand_")


# ---------------------------------------------------------------------
# 4. CANDIDATE MATCHING
# ---------------------------------------------------------------------

def test_candidate_matching(sample_candidate, sample_job):
    """Verify skill matching and experience scoring."""

    score = match_candidate_tool(
        sample_candidate,
        sample_job,
    )

    assert score.candidate_id == sample_candidate.candidate_id
    assert score.job_id == sample_job.job_id

    assert 0.0 <= score.score <= 100.0

    assert score.score == 82.5

    assert "python" in score.matched_skills
    assert "fastapi" in score.matched_skills
    assert "react" in score.matched_skills

    assert "docker" in score.missing_skills

    assert score.recommendation == (
        "Strong Match — Recommend Interview"
    )


def test_candidate_matching_with_no_required_skills():
    """Matching should handle a job without required skills."""

    candidate = CandidateProfile(
        candidate_id="candidate_empty_001",
        name="Test Candidate",
        email="test@example.com",
        years_experience=2.0,
        skills=["python"],
    )

    job = JobPosting(
        job_id="job_empty_001",
        title="General Engineer",
        department="Engineering",
        required_skills=[],
        min_years_experience=2.0,
    )

    score = match_candidate_tool(candidate, job)

    assert score.score == 100.0
    assert score.matched_skills == []
    assert score.missing_skills == []


# ---------------------------------------------------------------------
# 5. HUMAN-IN-THE-LOOP APPROVAL
# ---------------------------------------------------------------------

def test_hiring_offer_requires_approval(
    agent,
    recruiter_context,
):
    """Employment offers must pause for authorized human approval."""

    request = AgentRequest(
        query="make offer to candidate Jane Doe for Senior Developer",
        context=recruiter_context,
        parameters={
            "candidate_name": "Jane Doe",
            "job_title": "Senior Developer",
            "offered_salary": 1200000.0,
        },
    )

    response = agent.execute(request)

    assert response.status == ExecutionStatus.PENDING_APPROVAL

    approval = response.approval_request

    assert approval is not None

    assert approval.operation_name == "extend_employment_offer"

    assert approval.tenant_id == recruiter_context.tenant_id

    assert approval.product_id == ProductId.RECRUITMENT

    assert approval.status == ApprovalStatus.PENDING

    assert approval.payload["candidate_name"] == "Jane Doe"
    assert approval.payload["job_title"] == "Senior Developer"
    assert approval.payload["offered_salary"] == 1200000.0

    assert Role.HR_ADMIN in approval.required_roles

    # An offer must not be dispatched before approval.
    assert "NOT been dispatched" in response.response_text


def test_hiring_offer_requires_authorized_approval_role(
    agent,
    recruiter_context,
    guest_context,
):
    """Verify that an unauthorized guest cannot approve an offer."""

    request = AgentRequest(
        query="make offer to candidate Jane Doe",
        context=recruiter_context,
        parameters={
            "candidate_name": "Jane Doe",
            "job_title": "Developer",
            "offered_salary": 1000000.0,
        },
    )

    response = agent.execute(request)

    assert response.status == ExecutionStatus.PENDING_APPROVAL
    assert response.approval_request is not None

    from anycode.agents.products.shared_services import approval_service

    with pytest.raises(PermissionError):
        approval_service.decide(
            approval_id=response.approval_request.approval_id,
            context=guest_context,
            approve=True,
        )


def test_hiring_offer_can_be_approved_by_hr(
    agent,
    recruiter_context,
    hr_context,
):
    """Verify that an authorized HR administrator can approve an offer."""

    request = AgentRequest(
        query="make offer to candidate Jane Doe",
        context=recruiter_context,
        parameters={
            "candidate_name": "Jane Doe",
            "job_title": "Senior Developer",
            "offered_salary": 1200000.0,
        },
    )

    response = agent.execute(request)

    assert response.status == ExecutionStatus.PENDING_APPROVAL
    assert response.approval_request is not None

    from anycode.agents.products.shared_services import approval_service

    approval = approval_service.decide(
        approval_id=response.approval_request.approval_id,
        context=hr_context,
        approve=True,
    )

    assert approval.status == ApprovalStatus.APPROVED
    assert approval.decided_by == hr_context.user_id
    assert approval.tenant_id == recruiter_context.tenant_id


# ---------------------------------------------------------------------
# 6. TENANT ISOLATION
# ---------------------------------------------------------------------

def test_approval_cannot_be_decided_by_another_tenant(
    agent,
    recruiter_context,
):
    """An approval must not be accessible across tenant boundaries."""

    request = AgentRequest(
        query="make offer to candidate Jane Doe",
        context=recruiter_context,
        parameters={
            "candidate_name": "Jane Doe",
            "job_title": "Developer",
            "offered_salary": 1000000.0,
        },
    )

    response = agent.execute(request)

    assert response.approval_request is not None

    from anycode.agents.products.shared_services import approval_service

    foreign_tenant_context = TenantContext(
        tenant_id="different_tenant",
        user_id="foreign_hr_user",
        roles=[Role.HR_ADMIN],
    )

    with pytest.raises(PermissionError):
        approval_service.decide(
            approval_id=response.approval_request.approval_id,
            context=foreign_tenant_context,
            approve=True,
        )
