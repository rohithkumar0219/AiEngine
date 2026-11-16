"""Coworking Space services — domain business logic."""

from __future__ import annotations

from typing import List

from anycode.agents.products.coworking.schemas import Booking, Invoice, Seat


class BookingService:
    """Manages seat booking lifecycle."""

    def list_member_bookings(self, member_id: str, bookings: List[Booking]) -> List[Booking]:
        return [b for b in bookings if b.member_id == member_id]

    def total_member_spend(self, member_id: str, bookings: List[Booking]) -> float:
        return sum(
            b.amount
            for b in bookings
            if b.member_id == member_id and b.status in ("confirmed", "completed")
        )


class InvoiceService:
    """Invoice and payment management."""

    def mark_paid(self, invoice: Invoice) -> Invoice:
        invoice.paid = True
        return invoice

    def pending_invoices(self, member_id: str, invoices: List[Invoice]) -> List[Invoice]:
        return [i for i in invoices if i.member_id == member_id and not i.paid]


class SeatService:
    """Seat inventory management."""

    def reserve_seat(self, seat: Seat) -> bool:
        if not seat.is_available:
            return False
        seat.is_available = False
        return True

    def release_seat(self, seat: Seat) -> Seat:
        seat.is_available = True
        return seat
