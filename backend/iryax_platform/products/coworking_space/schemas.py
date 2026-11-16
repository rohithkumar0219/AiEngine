"""Typed schemas for Coworking Space Agent."""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class SpaceUnit(BaseModel):
    unit_id: str
    unit_type: str  # hot_desk, dedicated_desk, meeting_cabin, private_office
    name: str
    capacity: int
    hourly_rate_inr: float
    is_available: bool = True


class BookingProposal(BaseModel):
    booking_id: str
    member_id: str
    member_name: str
    unit_id: str
    unit_type: str
    start_time: str
    end_time: str
    total_hours: float
    estimated_cost: float
    status: str = "proposed"


class BookingConfirmation(BaseModel):
    booking_id: str
    unit_id: str
    member_name: str
    confirmed_time_slot: str
    access_code: str
    payment_status: str = "paid_confirmed"


class VisitorPass(BaseModel):
    pass_id: str
    visitor_name: str
    host_member: str
    valid_date: str
    access_zone: str = "Lobby & Conference Rooms"
    pass_code: str


class FacilityRequest(BaseModel):
    ticket_id: str
    unit_id: str
    issue_category: str  # ac_cooling, high_speed_wifi, cleaning, power_socket
    description: str
    priority: str = "medium"
    status: str = "open"
