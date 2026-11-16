"""Medical Camps domain schemas."""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class Patient(BaseModel):
    patient_id: str
    privacy_token: str          # anonymised identifier exposed externally
    name: str                   # PII – never logged
    age: int
    gender: str
    village: str
    phone: Optional[str] = None


class VitalReading(BaseModel):
    patient_id: str
    blood_pressure: str         # e.g. "120/80"
    pulse: int
    temperature: float          # °C
    spo2: int                   # %
    blood_glucose: Optional[float] = None   # mg/dL
    flag_triage: bool = False


class Volunteer(BaseModel):
    volunteer_id: str
    name: str
    role: str                   # e.g. "doctor", "nurse", "helper"
    shift: str                  # "morning" | "afternoon" | "full"
    is_confirmed: bool = False


class MedicalCamp(BaseModel):
    camp_id: str
    name: str
    location: str
    scheduled_date: str
    tenant_id: str
    organiser_id: str
    volunteers: List[Volunteer] = Field(default_factory=list)
    patient_registrations: int = 0
    status: str = "planned"     # planned | active | completed | cancelled


class CampSummary(BaseModel):
    camp_id: str
    total_patients: int
    triaged_critical: int
    triaged_moderate: int
    triaged_normal: int
    volunteer_count: int
    medicines_dispensed: int
    referrals_issued: int
    completion_percentage: float
