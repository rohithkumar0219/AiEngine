"""Coworking Space Product Agent."""

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
from iryax_platform.products.coworking_space.schemas import BookingProposal
from iryax_platform.products.coworking_space.service import CoworkingSpaceService


class CoworkingSpaceAgent(BaseProductAgent):
    """Product Agent for Iryax Coworking Space (desk & cabin bookings, visitor passes, facilities)."""

    product_id = ProductId.COWORKING_SPACE
    name = "Iryax Coworking Space Agent"
    description = (
        "Manages desk and meeting cabin availability, booking reservations, "
        "double-booking prevention, visitor passes, and facility requests."
    )
    supported_intents = [
        "check_space_availability",
        "book_space",
        "issue_visitor_pass",
        "facility_request",
        "request_refund",
        "general_workspace_query",
    ]
    required_roles = [Role.WORKSPACE_ADMIN, Role.COWORKING_MEMBER, Role.TENANT_ADMIN]

    def __init__(self, service: CoworkingSpaceService | None = None):
        super().__init__()
        self.service = service or CoworkingSpaceService()
        self._register_default_tools()

    def _register_default_tools(self):
        self.register_tool("check_space_availability", self.service.check_space_availability)
        self.register_tool("propose_booking", self.service.propose_booking)
        self.register_tool("confirm_booking", self.service.confirm_booking)
        self.register_tool("issue_visitor_pass", self.service.issue_visitor_pass)
        self.register_tool("submit_facility_request", self.service.submit_facility_request)
        self.register_tool("create_refund_approval", self.service.create_refund_approval)

    def handle_request(self, request: AgentRequest) -> AgentResponse:
        query_lower = request.query.lower()
        tools_executed: List[ToolCallRecord] = []

        # 1. Guardrail: Refund or access control level modifications
        if any(w in query_lower for w in ("refund", "money back", "cancel and refund", "grant security access")):
            bid = request.parameters.get("booking_id", "bk_sample_01")
            amt = float(request.parameters.get("refund_amount", 400.0))
            reason = request.parameters.get("reason", request.query)

            call_record = self.execute_tool(
                "create_refund_approval",
                {
                    "context": request.context,
                    "booking_id": bid,
                    "refund_amount": amt,
                    "reason": reason,
                },
                request.context,
            )
            tools_executed.append(call_record)
            approval_req = call_record.output

            return AgentResponse(
                product_id=self.product_id,
                status=ExecutionStatus.PENDING_APPROVAL,
                response_text=(
                    f"Financial Policy: Direct automated issuance of booking refunds is restricted. "
                    f"A refund approval request (ID: {approval_req.approval_id}) has been created for "
                    f"INR {amt:,.2f} on booking {bid}. Workspace Admin authorization is required."
                ),
                structured_data={"approval_id": approval_req.approval_id, "status": "pending_approval"},
                tools_executed=tools_executed,
                approval_request=approval_req,
            )

        # 2. Check workspace availability
        if any(w in query_lower for w in ("desk", "cabin", "available", "spaces", "workstation", "room")):
            unit_type = request.parameters.get("unit_type")
            call_record = self.execute_tool("check_space_availability", {"unit_type": unit_type}, request.context)
            tools_executed.append(call_record)
            units = call_record.output

            units_str = "; ".join([f"{u.name} ({u.unit_type}, Cap: {u.capacity}, INR {u.hourly_rate_inr}/hr)" for u in units])
            return AgentResponse(
                product_id=self.product_id,
                status=ExecutionStatus.SUCCESS,
                response_text=f"Available coworking spaces: {units_str}",
                structured_data={"spaces": [u.model_dump() for u in units]},
                tools_executed=tools_executed,
            )

        # 3. Book a desk or cabin (with double-booking check and confirmation)
        if any(w in query_lower for w in ("book", "reserve", "meeting room", "reserve desk")):
            unit_id = request.parameters.get("unit_id", "cabin_focus_01")
            start = request.parameters.get("start_time", "14:00")
            end = request.parameters.get("end_time", "16:00")
            hours = float(request.parameters.get("hours", 2.0))
            member_name = request.parameters.get("member_name", "Member")

            # Try creating proposal
            try:
                call_record = self.execute_tool(
                    "propose_booking",
                    {
                        "member_id": request.context.user_id,
                        "member_name": member_name,
                        "unit_id": unit_id,
                        "start_time": start,
                        "end_time": end,
                        "hours": hours,
                    },
                    request.context,
                )
                tools_executed.append(call_record)
                if call_record.status == "failed":
                    raise ValueError(call_record.output.get("error", "Booking proposal failed"))

                proposal: BookingProposal = call_record.output

                # Confirm booking atomically
                confirm_call = self.execute_tool("confirm_booking", {"proposal": proposal}, request.context)
                tools_executed.append(confirm_call)
                if confirm_call.status == "failed":
                    raise ValueError(confirm_call.output.get("error", "Booking confirmation failed"))

                confirmation = confirm_call.output

                return AgentResponse(
                    product_id=self.product_id,
                    status=ExecutionStatus.SUCCESS,
                    response_text=(
                        f"Booking confirmed for {proposal.unit_id} ({confirmation.confirmed_time_slot}) "
                        f"for {member_name}. Total Cost: INR {proposal.estimated_cost:,.2f}. "
                        f"Access Door Code: {confirmation.access_code} (Booking ID: {confirmation.booking_id})."
                    ),
                    structured_data={
                        "proposal": proposal.model_dump(),
                        "confirmation": confirmation.model_dump(),
                    },
                    tools_executed=tools_executed,
                )
            except ValueError as ve:
                return AgentResponse(
                    product_id=self.product_id,
                    status=ExecutionStatus.FAILED,
                    response_text=f"Reservation Collision Error: {str(ve)}",
                    tools_executed=tools_executed,
                )

        # 4. Visitor pass
        if any(w in query_lower for w in ("visitor", "guest pass", "visitor badge")):
            vname = request.parameters.get("visitor_name", "Visitor Guest")
            host = request.parameters.get("host_member", "Iryax Member")

            call_record = self.execute_tool(
                "issue_visitor_pass",
                {"visitor_name": vname, "host_member": host},
                request.context,
            )
            tools_executed.append(call_record)
            pass_obj = call_record.output

            return AgentResponse(
                product_id=self.product_id,
                status=ExecutionStatus.SUCCESS,
                response_text=(
                    f"Generated visitor access pass for {vname} (Host: {host}). "
                    f"Pass Code: {pass_obj.pass_code} (Valid for {pass_obj.access_zone})."
                ),
                structured_data=pass_obj.model_dump(),
                tools_executed=tools_executed,
            )

        # 5. Check live backend sync
        if "sync" in query_lower or "workspace api" in query_lower:
            if not self.service.is_backend_connected():
                return AgentResponse(
                    product_id=self.product_id,
                    status=ExecutionStatus.BLOCKED_BACKEND,
                    response_text=(
                        "Live Iryax Coworking Space backend service is not configured in this environment "
                        "(missing WORKSPACE_API_URL). Local space lookup, collision detection, and pass issuance remain operational."
                    ),
                    backend_supported=False,
                    missing_backend_message="Missing WORKSPACE_API_URL",
                )

        # 6. Default
        return AgentResponse(
            product_id=self.product_id,
            status=ExecutionStatus.SUCCESS,
            response_text=(
                "Iryax Coworking Space Agent is ready. You can query available desks and cabins, "
                "book meeting spaces with double-booking prevention, issue visitor passes, or submit facility tickets."
            ),
            tools_executed=[],
        )
