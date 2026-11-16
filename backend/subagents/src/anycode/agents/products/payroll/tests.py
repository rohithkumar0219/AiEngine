"""Unit and regression tests for Payroll Product Agent."""

from __future__ import annotations

import pytest
from anycode.agents.products.payroll.agent import PayrollAgent
from anycode.agents.products.payroll.schemas import AttendanceRecord
from anycode.agents.products.payroll.tools import calculate_draft_payroll_tool, reconcile_attendance_tool
from anycode.agents.products.shared_schemas import (
    AgentRequest,
    ExecutionStatus,
    ProductId,
    Role,
    TenantContext,
)


@pytest.fixture
def payroll_admin_context():
    return TenantContext(tenant_id="tenant_pay_01", user_id="admin_01", roles=[Role.PAYROLL_ADMIN])


@pytest.fixture
def unauthorized_context():
    return TenantContext(tenant_id="tenant_pay_01", user_id="guest_01", roles=[Role.GUEST])


@pytest.fixture
def agent():
    return PayrollAgent()


def test_payroll_agent_metadata(agent):
    assert agent.product_id == ProductId.PAYROLL
    assert "reconcile_attendance" in agent.list_tools()


def test_payroll_rbac_denied(agent, unauthorized_context):
    req = AgentRequest(query="calculate payroll", context=unauthorized_context)
    resp = agent.execute(req)
    assert resp.status == ExecutionStatus.PERMISSION_DENIED
    assert "Access Denied" in resp.response_text


def test_attendance_reconciliation():
    records = [
        AttendanceRecord(employee_id="E1", employee_name="Alice", date="2026-10-01", check_in="09:00", check_out="18:00", hours_worked=9.0),
        AttendanceRecord(employee_id="E2", employee_name="Bob", date="2026-10-01", check_in="09:00", check_out="23:30", hours_worked=14.5),
    ]
    res = reconcile_attendance_tool(records)
    assert res["total_records_processed"] == 2
    assert len(res["anomalies_detected"]) == 1
    assert res["anomalies_detected"][0]["anomaly_type"] == "excessive_overtime"


def test_draft_payroll_computation():
    draft = calculate_draft_payroll_tool("E1", "Alice", 66000.0, 22, overtime_hours=4.0)
    assert draft.base_salary == 66000.0
    assert draft.overtime_pay > 0
    assert draft.net_salary > 0
    assert draft.payment_status == "draft_unpaid"


def test_disbursement_requires_human_approval(agent, payroll_admin_context):
    req = AgentRequest(
        query="release payment of INR 300000 for October payroll cycle",
        context=payroll_admin_context,
        parameters={"cycle": "2026-10", "total_amount": 300000.0, "recipient_count": 10},
    )
    resp = agent.execute(req)
    assert resp.status == ExecutionStatus.PENDING_APPROVAL
    assert resp.approval_request is not None
    assert resp.approval_request.operation_name == "release_payment"
