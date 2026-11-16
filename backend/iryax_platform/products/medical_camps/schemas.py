"""Typed schemas for Medical Camps Agent."""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class CampPlan(BaseModel):
    camp_id: str
    camp_name: str
    location: str
    target_date: str
    expected_attendees: int
    participating_doctors: List[str] = Field(default_factory=list)
    volunteer_count: int = 0
    status: str = "planned"


class PatientRegistration(BaseModel):
    registration_id: str
    camp_id: str
    patient_token: str  # Pseudonymized token for privacy
    age: int
    gender: str
    chief_complaint: str
    registered_at: str


class VitalValidation(BaseModel):
    patient_token: str
    systolic_bp: int
    diastolic_bp: int
    pulse_rate: int
    blood_glucose_mg_dl: Optional[float] = None
    is_abnormal: bool = False
    flagged_reasons: List[str] = Field(default_factory=list)
    clinical_disclaimer: str = (
        "Non-diagnostic validation. Flags indicate measurements outside statistical "
        "norms and must be evaluated directly by a licensed medical practitioner."
    )


class ResourceInventory(BaseModel):
    camp_id: str
    first_aid_kits: int
    bp_monitors: int
    glucometers: int
    glucose_strips: int
    volunteer_badges: int


class AggregateCampReport(BaseModel):
    camp_id: str
    camp_name: str
    total_registered_patients: int
    patients_with_vital_flags: int
    resources_utilized_percentage: float
    doctors_present: int
    volunteers_active: int
