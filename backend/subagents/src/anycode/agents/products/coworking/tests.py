"""Unit and regression tests for Coworking Space Agent."""

from __future__ import annotations

import pytest
from anycode.agents.products.coworking.agent import CoworkingAgent
from anycode.agents.products.coworking.schemas import Booking, Seat
from anycode.agents.products.coworking.tools import (
    book_seat_tool,
    cancel_booking_tool,
    check_seat_availability_tool,
)
from anycode.agents.products.shared_schemas import (
    AgentRequest,
    ExecutionStatus,
    ProductId,
    Role,
    TenantContext,
)


@pytest.fixture
def member_context():
    return TenantContext(
        tenant_id="tenant_cw_01",
        user_id="member_01",
        roles=[Role.COWORKING_MEMBER],
    )


@pytest.fixture
def unauthorized_context():
    return TenantContext(
        tenant_id="tenant_cw_01",
        user_id="guest_01",
        roles=[Role.GUEST],
    )


@pytest.fixture
def agent():
    return CoworkingAgent()


def test_coworking_agent_metadata(agent):
    assert agent.product_id == ProductId.COWORKING
    assert "book_seat" in agent.list_tools()
    assert "occupancy_report" in agent.list_tools()


def test_coworking_agent_rbac_denied(agent, unauthorized_context):
    req = AgentRequest(query="book seat", context=unauthorized_context)
    resp = agent.execute(req)
    assert resp.status == ExecutionStatus.PERMISSION_DENIED


def test_seat_availability():
    seats = [
        Seat(seat_id="S1", location="Floor-1", seat_type="hot_desk", is_available=True),
        Seat(seat_id="S2", location="Floor-1", seat_type="hot_desk", is_available=False),
        Seat(seat_id="S3", location="Floor-2", seat_type="dedicated", is_available=True),
    ]
    available = check_seat_availability_tool(seats, seat_type="hot_desk")
    assert len(available) == 1
    assert available[0].seat_id == "S1"


def test_book_seat():
    booking = book_seat_tool(
        member_id="member_01",
        seat_id="S1",
        date="2024-02-15",
        start_time="09:00",
        end_time="17:00",
        amount=400.0,
        tenant_id="tenant_cw_01",
    )
    assert booking.booking_id.startswith("BKG-")
    assert booking.status == "confirmed"
    assert booking.amount == 400.0


def test_cancel_booking_refund_eligible():
    booking = Booking(
        booking_id="BKG-001",
        member_id="member_01",
        seat_id="S1",
        date="2024-02-15",
        start_time="09:00",
        end_time="17:00",
        amount=1500.0,          # above REFUND_THRESHOLD_INR (1000)
        tenant_id="tenant_cw_01",
    )
    updated, refund_eligible = cancel_booking_tool(booking)
    assert updated.status == "cancelled"
    assert refund_eligible is True


def test_refund_requires_approval(agent, member_context):
    req = AgentRequest(
        query="process refund for my booking",
        context=member_context,
        parameters={"booking_id": "BKG-001", "amount": 2000.0},
    )
    resp = agent.execute(req)
    assert resp.status == ExecutionStatus.PENDING_APPROVAL
    assert resp.approval_request.operation_name == "refund_or_invoice_adjustment"
