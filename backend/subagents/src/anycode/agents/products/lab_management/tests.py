"""Unit and regression tests for Lab Management Agent."""

from __future__ import annotations

import pytest
from anycode.agents.products.lab_management.agent import LabManagementAgent
from anycode.agents.products.lab_management.tools import (
    create_lab_order_tool,
    enter_results_tool,
    release_result_tool,
)
from anycode.agents.products.shared_schemas import (
    AgentRequest,
    ExecutionStatus,
    ProductId,
    Role,
    TenantContext,
)


@pytest.fixture
def technician_context():
    return TenantContext(
        tenant_id="tenant_lab_01",
        user_id="tech_01",
        roles=[Role.LAB_TECHNICIAN],
    )


@pytest.fixture
def pathologist_context():
    return TenantContext(
        tenant_id="tenant_lab_01",
        user_id="path_01",
        roles=[Role.PATHOLOGIST],
    )


@pytest.fixture
def unauthorized_context():
    return TenantContext(
        tenant_id="tenant_lab_01",
        user_id="guest_01",
        roles=[Role.GUEST],
    )


@pytest.fixture
def agent():
    return LabManagementAgent()


def test_lab_agent_metadata(agent):
    assert agent.product_id == ProductId.LAB_MANAGEMENT
    assert "create_lab_order" in agent.list_tools()
    assert "release_result" in agent.list_tools()


def test_lab_agent_rbac_denied(agent, unauthorized_context):
    req = AgentRequest(query="create order", context=unauthorized_context)
    resp = agent.execute(req)
    assert resp.status == ExecutionStatus.PERMISSION_DENIED


def test_create_lab_order():
    order = create_lab_order_tool(
        patient_id="PT-001",
        ordered_by="DOC-001",
        test_ids=["CBC", "LFT", "KFT"],
        priority="routine",
        tenant_id="tenant_lab_01",
    )
    assert order.order_id.startswith("LAB-")
    assert len(order.test_ids) == 3
    assert order.priority == "routine"


def test_abnormal_result_flagging():
    result = enter_results_tool(
        sample_id="SMP-001",
        patient_id="PT-001",
        test_id="CBC",
        values={"haemoglobin": 7.5},         # low (<12 normal low)
        reference_range={"haemoglobin": {"low": 12.0, "high": 17.5}},
    )
    assert result.flag_abnormal is True
    assert result.released is False


def test_normal_result_not_flagged():
    result = enter_results_tool(
        sample_id="SMP-002",
        patient_id="PT-002",
        test_id="CBC",
        values={"haemoglobin": 14.2},
        reference_range={"haemoglobin": {"low": 12.0, "high": 17.5}},
    )
    assert result.flag_abnormal is False


def test_result_release_requires_approval(agent, technician_context):
    req = AgentRequest(
        query="release result for order LAB-1234",
        context=technician_context,
        parameters={"order_id": "LAB-1234"},
    )
    resp = agent.execute(req)
    assert resp.status == ExecutionStatus.PENDING_APPROVAL
    assert resp.approval_request.operation_name == "release_lab_results"


def test_release_result_tool():
    result = enter_results_tool(
        sample_id="SMP-003",
        patient_id="PT-003",
        test_id="LFT",
        values={"ALT": 32},
        reference_range={"ALT": {"low": 7, "high": 56}},
    )
    released = release_result_tool(result, verified_by="path_01")
    assert released.released is True
    assert released.verified_by == "path_01"
