"""Coworking Space domain schemas."""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class CoworkingMember(BaseModel):
    member_id: str
    name: str
    email: str
    plan: str                   # "hot_desk" | "dedicated" | "private_office" | "virtual"
    tenant_id: str
    is_active: bool = True


class Seat(BaseModel):
    seat_id: str
    location: str
    seat_type: str              # "hot_desk" | "dedicated" | "conference_room" | "private_cabin"
    capacity: int = 1
    amenities: List[str] = Field(default_factory=list)
    is_available: bool = True


class Booking(BaseModel):
    booking_id: str
    member_id: str
    seat_id: str
    date: str
    start_time: str
    end_time: str
    status: str = "confirmed"   # confirmed | cancelled | completed | pending_payment
    amount: float = 0.0
    tenant_id: str


class Invoice(BaseModel):
    invoice_id: str
    member_id: str
    booking_ids: List[str]
    period: str
    total_amount: float
    paid: bool = False
    due_date: str
    refund_eligible: bool = False


class SpaceSummary(BaseModel):
    date: str
    total_seats: int
    occupied_seats: int
    available_seats: int
    revenue_today: float
    active_members: int
    occupancy_rate: float
