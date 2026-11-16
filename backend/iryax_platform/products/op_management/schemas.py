"""Typed schemas for OP Management Agent."""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class DoctorAvailability(BaseModel):
    doctor_id: str
    doctor_name: str
    specialty: str
    available_date: str
    available_slots: List[str]


class AppointmentBooking(BaseModel):
    appointment_id: str
    patient_id: str
    patient_name: str
    doctor_name: str
    specialty: str
    slot_time: str
    token_number: int
    status: str = "confirmed"


class TokenQueueStatus(BaseModel):
    department: str
    doctor_name: str
    current_token_serving: int
    total_tokens_issued: int
    estimated_wait_minutes_per_token: int = 10


class BillingSummary(BaseModel):
    invoice_id: str
    patient_id: str
    consultation_fee: float
    procedure_fees: float = 0.0
    medication_estimate: float = 0.0
    total_amount: float
    payment_status: str = "pending"
