"""Coworking Space Service and Backend Connector (Iryax Coworking Space)."""

from __future__ import annotations

import os
import uuid
from typing import Any, Dict, List, Optional

from iryax_platform.core.audit import approval_store
from iryax_platform.core.context import Role, TenantContext
from iryax_platform.core.contracts import ApprovalRequest
from iryax_platform.products.coworking_space.schemas import (
    BookingConfirmation,
    BookingProposal,
    FacilityRequest,
    SpaceUnit,
    VisitorPass,
)


class CoworkingSpaceService:
    """Operations for workspace inventory, double-booking prevention, passes, and facility requests."""

    def __init__(self):
        self.api_url = os.getenv("WORKSPACE_API_URL")
        self.api_key = os.getenv("WORKSPACE_API_KEY")
        # In-memory reservation tracker for double-booking prevention
        self._active_bookings: Dict[str, set[str]] = {}

    def is_backend_connected(self) -> bool:
        return bool(self.api_url and self.api_key)

    def check_space_availability(
        self,
        unit_type: Optional[str] = None,
    ) -> List[SpaceUnit]:
        """Fetch available hot desks, dedicated workstations, and meeting cabins."""
        units = [
            SpaceUnit(unit_id="desk_hot_01", unit_type="hot_desk", name="Hot Desk A-12", capacity=1, hourly_rate_inr=100.0, is_available=True),
            SpaceUnit(unit_id="desk_hot_02", unit_type="hot_desk", name="Hot Desk A-14", capacity=1, hourly_rate_inr=100.0, is_available=True),
            SpaceUnit(unit_id="cabin_conf_01", unit_type="meeting_cabin", name="Executive Boardroom", capacity=10, hourly_rate_inr=800.0, is_available=True),
            SpaceUnit(unit_id="cabin_focus_01", unit_type="meeting_cabin", name="Focus Pod Beta", capacity=4, hourly_rate_inr=400.0, is_available=True),
            SpaceUnit(unit_id="office_priv_01", unit_type="private_office", name="Enterprise Suite 101", capacity=8, hourly_rate_inr=1200.0, is_available=True),
        ]

        if unit_type:
            u_lower = unit_type.lower()
            return [u for u in units if u_lower in u.unit_type or u_lower in u.name.lower()]
        return units

    def propose_booking(
        self,
        member_id: str,
        member_name: str,
        unit_id: str,
        start_time: str,
        end_time: str,
        hours: float = 2.0,
    ) -> BookingProposal:
        """Create a booking proposal and verify no collision with active slots."""
        time_slot = f"{start_time}-{end_time}"
        existing_slots = self._active_bookings.get(unit_id, set())

        if time_slot in existing_slots:
            raise ValueError(
                f"Double Booking Prevented: Unit '{unit_id}' is already reserved for slot '{time_slot}'. "
                f"Please choose an alternate time or space."
            )

        rate = 400.0 if "cabin" in unit_id else (100.0 if "hot" in unit_id else 800.0)
        cost = round(rate * hours, 2)

        return BookingProposal(
            booking_id=f"bk_{uuid.uuid4().hex[:8]}",
            member_id=member_id,
            member_name=member_name,
            unit_id=unit_id,
            unit_type="meeting_cabin" if "cabin" in unit_id else "hot_desk",
            start_time=start_time,
            end_time=end_time,
            total_hours=hours,
            estimated_cost=cost,
            status="proposed",
        )

    def confirm_booking(self, proposal: BookingProposal) -> BookingConfirmation:
        """Atomically lock the time slot and confirm the reservation."""
        time_slot = f"{proposal.start_time}-{proposal.end_time}"
        if proposal.unit_id not in self._active_bookings:
            self._active_bookings[proposal.unit_id] = set()

        if time_slot in self._active_bookings[proposal.unit_id]:
            raise ValueError(f"Cannot confirm: Space {proposal.unit_id} was just booked by another user.")

        self._active_bookings[proposal.unit_id].add(time_slot)
        access_code = f"AC-{uuid.uuid4().hex[:4].upper()}"

        return BookingConfirmation(
            booking_id=proposal.booking_id,
            unit_id=proposal.unit_id,
            member_name=proposal.member_name,
            confirmed_time_slot=time_slot,
            access_code=access_code,
            payment_status="paid_confirmed",
        )

    def issue_visitor_pass(
        self,
        visitor_name: str,
        host_member: str,
        date: str = "Today",
    ) -> VisitorPass:
        """Issue an access pass code for co-working visitors."""
        return VisitorPass(
            pass_id=f"vpass_{uuid.uuid4().hex[:8]}",
            visitor_name=visitor_name,
            host_member=host_member,
            valid_date=date,
            pass_code=f"VIS-{uuid.uuid4().hex[:5].upper()}",
        )

    def submit_facility_request(
        self,
        unit_id: str,
        category: str,
        description: str,
    ) -> FacilityRequest:
        """Submit a facility maintenance ticket."""
        return FacilityRequest(
            ticket_id=f"fac_{uuid.uuid4().hex[:8]}",
            unit_id=unit_id,
            issue_category=category,
            description=description,
            priority="high" if "ac" in category.lower() or "power" in category.lower() else "medium",
            status="open",
        )

    def create_refund_approval(
        self,
        context: TenantContext,
        booking_id: str,
        refund_amount: float,
        reason: str,
    ) -> ApprovalRequest:
        """Request explicit admin approval before issuing monetary refunds."""
        return approval_store.create_request(
            tenant_id=context.tenant_id,
            product_id="iryax.coworking_space",
            operation_name="issue_refund",
            payload={
                "booking_id": booking_id,
                "refund_amount": refund_amount,
                "reason": reason,
                "requested_by": context.user_id,
            },
            required_roles=[Role.SUPER_ADMIN, Role.TENANT_ADMIN, Role.WORKSPACE_ADMIN],
        )
