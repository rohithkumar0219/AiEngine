"""Unit and regression tests for Medical Camps Agent."""

from __future__ import annotations

import pytest
from anycode.agents.products.medical_camps.agent import MedicalCampsAgent
from anycode.agents.products.medical_camps.tools import (
    register_patient_tool,
    validate_vitals_tool,
)
from anycode.agents.products.shared_schemas import (
    AgentRequest,
    ExecutionStatus,
    ProductId,
    Role,
    TenantContext,
)


@pytest.fixture
def coordinator_context():
    return TenantContext(
        tenant_id="tenant_camp_01",
        user_id="coord_01",
        roles=[Role.CAMP_COORDINATOR],
    )


@pytest.fixture
def unauthorized_context():
    return TenantContext(
        tenant_id="tenant_camp_01",
        user_id="guest_01",
        roles=[Role.GUEST],
    )


@pytest.fixture
def agent():
    return MedicalCampsAgent()


def test_camp_agent_metadata(agent):
    assert agent.product_id == ProductId.MEDICAL_CAMPS
    assert "create_camp" in agent.list_tools()
    assert "validate_vitals" in agent.list_tools()


def test_camp_agent_rbac_denied(agent, unauthorized_context):
    req = AgentRequest(query="plan camp", context=unauthorized_context)
    resp = agent.execute(req)
    assert resp.status == ExecutionStatus.PERMISSION_DENIED


def test_patient_registration():
    patient = register_patient_tool(
        name="Ananya Kumar",
        age=35,
        gender="F",
        village="Kovilpatti",
        phone="9876543210",
    )
    assert patient.privacy_token.startswith("CAMP-")
    assert patient.patient_id.startswith("PT-")
    # Name must be in the object but NEVER returned in agent responses
    assert patient.name == "Ananya Kumar"


def test_vitals_triage_critical():
    vitals = validate_vitals_tool(
        patient_id="PT-TEST",
        blood_pressure="190/100",   # systolic >= 180 → critical
        pulse=88,
        temperature=37.5,
        spo2=96,
    )
    assert vitals.flag_triage is True


def test_vitals_triage_normal():
    vitals = validate_vitals_tool(
        patient_id="PT-TEST",
        blood_pressure="118/76",
        pulse=72,
        temperature=37.0,
        spo2=98,
    )
    assert vitals.flag_triage is False


def test_bulk_data_export_requires_approval(agent, coordinator_context):
    req = AgentRequest(
        query="release result and export patient data dump",
        context=coordinator_context,
        parameters={"camp_id": "CAMP-ABC1"},
    )
    resp = agent.execute(req)
    assert resp.status == ExecutionStatus.PENDING_APPROVAL
    assert resp.approval_request is not None
    assert resp.approval_request.operation_name == "bulk_patient_data_export"
