"""Coworking Space domain tools."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import List

from anycode.agents.products.coworking.config import (
    CANCELLATION_WINDOW_HOURS,
    REFUND_THRESHOLD_INR,
)
from anycode.agents.products.coworking.schemas import (
    Booking,
    Invoice,
    Seat,
    SpaceSummary,
)


def check_seat_availability_tool(seats: List[Seat], seat_type: str = "") -> List[Seat]:
    """Return seats that are available, optionally filtered by type."""
    available = [s for s in seats if s.is_available]
    if seat_type:
        available = [s for s in available if s.seat_type == seat_type]
    return available


def book_seat_tool(
    member_id: str,
    seat_id: str,
    date: str,
    start_time: str,
    end_time: str,
    amount: float,
    tenant_id: str,
) -> Booking:
    """Create a confirmed seat booking."""
    return Booking(
        booking_id=f"BKG-{secrets.token_hex(4).upper()}",
        member_id=member_id,
        seat_id=seat_id,
        date=date,
        start_time=start_time,
        end_time=end_time,
        status="confirmed",
        amount=amount,
        tenant_id=tenant_id,
    )


def cancel_booking_tool(booking: Booking, reason: str = "") -> tuple[Booking, bool]:
    """
    Cancel a booking. Returns (updated_booking, refund_eligible).
    Refund is eligible when booking amount exceeds REFUND_THRESHOLD_INR.
    """
    booking.status = "cancelled"
    refund_eligible = booking.amount >= REFUND_THRESHOLD_INR
    return booking, refund_eligible


def generate_invoice_tool(
    member_id: str,
    booking_ids: List[str],
    period: str,
    total_amount: float,
    due_date: str,
) -> Invoice:
    """Generate a membership invoice."""
    return Invoice(
        invoice_id=f"INV-{secrets.token_hex(4).upper()}",
        member_id=member_id,
        booking_ids=booking_ids,
        period=period,
        total_amount=total_amount,
        paid=False,
        due_date=due_date,
    )


def generate_occupancy_report_tool(
    date: str,
    seats: List[Seat],
    bookings: List[Booking],
) -> SpaceSummary:
    """Produce a daily occupancy and revenue summary."""
    total = len(seats)
    occupied = sum(1 for b in bookings if b.status == "confirmed")
    available = total - occupied
    revenue = sum(b.amount for b in bookings if b.status in ("confirmed", "completed"))
    return SpaceSummary(
        date=date,
        total_seats=total,
        occupied_seats=occupied,
        available_seats=available,
        revenue_today=revenue,
        active_members=len({b.member_id for b in bookings}),
        occupancy_rate=round(occupied / max(total, 1) * 100, 1),
    )
