"""Unit and regression tests for Task Management Agent."""

from __future__ import annotations

import pytest
from anycode.agents.products.shared_schemas import (
    AgentRequest,
    ExecutionStatus,
    ProductId,
    Role,
    TenantContext,
)
from anycode.agents.products.task_management.agent import TaskManagementAgent
from anycode.agents.products.task_management.schemas import TaskItem
from anycode.agents.products.task_management.tools import decompose_task_tool, detect_blockers_tool


@pytest.fixture
def task_lead_context():
    return TenantContext(tenant_id="tenant_task_01", user_id="lead_01", roles=[Role.TASK_LEAD])


@pytest.fixture
def unauthorized_context():
    return TenantContext(tenant_id="tenant_task_01", user_id="guest_01", roles=[Role.GUEST])


@pytest.fixture
def agent():
    return TaskManagementAgent()


def test_task_agent_metadata(agent):
    assert agent.product_id == ProductId.TASK_MANAGEMENT
    assert "create_task" in agent.list_tools()


def test_task_rbac_denied(agent, unauthorized_context):
    req = AgentRequest(query="create task", context=unauthorized_context)
    resp = agent.execute(req)
    assert resp.status == ExecutionStatus.PERMISSION_DENIED


def test_task_decomposition():
    decomp = decompose_task_tool("User Authentication Module", "Implement OAuth2 and JWT flow")
    assert len(decomp.subtasks) == 3
    assert decomp.estimated_total_hours > 0
    assert "1. Spec & Contracts" in decomp.subtasks[0].title


def test_blocker_detection():
    tasks = [
        TaskItem(task_id="t1", title="Database Setup", description="DB", status="in_progress"),
        TaskItem(task_id="t2", title="API Endpoint", description="API", status="blocked", dependencies=["t1"]),
    ]
    blockers = detect_blockers_tool(tasks)
    assert len(blockers) == 1
    assert blockers[0].task_title == "API Endpoint"
    assert blockers[0].blocked_by_title == "Database Setup"


def test_bulk_deletion_requires_approval(agent, task_lead_context):
    req = AgentRequest(
        query="bulk delete 50 archived tasks",
        context=task_lead_context,
        parameters={"task_count": 50, "action": "bulk_delete"},
    )
    resp = agent.execute(req)
    assert resp.status == ExecutionStatus.PENDING_APPROVAL
    assert resp.approval_request is not None
    assert resp.approval_request.operation_name == "delete_bulk_tasks"
