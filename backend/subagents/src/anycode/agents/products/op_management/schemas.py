"""OP Management domain schemas."""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class Patient(BaseModel):
    patient_id: str
    name: str                   # PII
    age: int
    gender: str
    contact: Optional[str] = None
    medical_history: List[str] = Field(default_factory=list)


class Appointment(BaseModel):
    appointment_id: str
    patient_id: str
    doctor_id: str
    department: str
    slot_time: str
    status: str = "scheduled"   # scheduled | checked_in | in_progress | completed | cancelled
    token_number: Optional[int] = None
    notes: Optional[str] = None


class DoctorSchedule(BaseModel):
    doctor_id: str
    name: str
    department: str
    available_slots: List[str]
    booked_slots: List[str] = Field(default_factory=list)
    max_daily_patients: int = 30


class Token(BaseModel):
    token_id: str
    appointment_id: str
    token_number: int
    issued_at: str
    estimated_wait_minutes: int
    counter: str


class OPSummary(BaseModel):
    date: str
    total_appointments: int
    completed: int
    cancelled: int
    waiting: int
    average_wait_minutes: float
    departments: List[str]
