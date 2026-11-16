"""Unit and regression tests for OP Management Agent."""

from __future__ import annotations

import pytest
from anycode.agents.products.op_management.agent import OPManagementAgent
from anycode.agents.products.op_management.schemas import Appointment, DoctorSchedule
from anycode.agents.products.op_management.tools import (
    book_appointment_tool,
    check_doctor_availability_tool,
    issue_token_tool,
)
from anycode.agents.products.shared_schemas import (
    AgentRequest,
    ExecutionStatus,
    ProductId,
    Role,
    TenantContext,
)


@pytest.fixture
def receptionist_context():
    return TenantContext(
        tenant_id="tenant_op_01",
        user_id="reception_01",
        roles=[Role.RECEPTIONIST],
    )


@pytest.fixture
def unauthorized_context():
    return TenantContext(
        tenant_id="tenant_op_01",
        user_id="guest_01",
        roles=[Role.GUEST],
    )


@pytest.fixture
def agent():
    return OPManagementAgent()


def test_op_agent_metadata(agent):
    assert agent.product_id == ProductId.OP_MANAGEMENT
    assert "book_appointment" in agent.list_tools()
    assert "issue_token" in agent.list_tools()


def test_op_agent_rbac_denied(agent, unauthorized_context):
    req = AgentRequest(query="book appointment", context=unauthorized_context)
    resp = agent.execute(req)
    assert resp.status == ExecutionStatus.PERMISSION_DENIED


def test_book_appointment():
    apt = book_appointment_tool(
        patient_id="PT-001",
        doctor_id="DOC-001",
        department="Cardiology",
        slot_time="10:00",
    )
    assert apt.appointment_id.startswith("APT-")
    assert apt.status == "scheduled"
    assert apt.department == "Cardiology"


def test_doctor_availability():
    schedule = DoctorSchedule(
        doctor_id="DOC-001",
        name="Dr. Rao",
        department="Cardiology",
        available_slots=["09:00", "10:00", "11:00"],
        booked_slots=["09:00"],
    )
    assert check_doctor_availability_tool(schedule, "10:00") is True
    assert check_doctor_availability_tool(schedule, "09:00") is False


def test_issue_token():
    apt = Appointment(
        appointment_id="APT-001",
        patient_id="PT-001",
        doctor_id="DOC-001",
        department="General",
        slot_time="09:00",
    )
    token = issue_token_tool(apt, token_number=5, counter="Counter-2")
    assert token.token_number == 5
    assert token.estimated_wait_minutes == 75   # 5 × 15 min default
    assert apt.status == "checked_in"


def test_schedule_override_requires_approval(agent, receptionist_context):
    req = AgentRequest(
        query="override schedule and force appointment for Dr. Rao",
        context=receptionist_context,
        parameters={"doctor_id": "DOC-001"},
    )
    resp = agent.execute(req)
    assert resp.status == ExecutionStatus.PENDING_APPROVAL
    assert resp.approval_request.operation_name == "doctor_schedule_override"
