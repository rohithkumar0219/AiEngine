"""Medical Camps domain tools."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import List

from anycode.agents.products.medical_camps.config import (
    PRIVACY_TOKEN_PREFIX,
    TRIAGE_CRITICAL_BP_SYSTOLIC,
    TRIAGE_CRITICAL_SPO2_THRESHOLD,
)
from anycode.agents.products.medical_camps.schemas import (
    CampSummary,
    MedicalCamp,
    Patient,
    VitalReading,
    Volunteer,
)
from anycode.agents.products.shared_schemas import ToolCallRecord


def create_camp_tool(
    name: str,
    location: str,
    scheduled_date: str,
    tenant_id: str,
    organiser_id: str,
) -> MedicalCamp:
    """Create a new medical camp record."""
    camp = MedicalCamp(
        camp_id=f"CAMP-{secrets.token_hex(4).upper()}",
        name=name,
        location=location,
        scheduled_date=scheduled_date,
        tenant_id=tenant_id,
        organiser_id=organiser_id,
        status="planned",
    )
    return camp


def register_patient_tool(
    name: str,
    age: int,
    gender: str,
    village: str,
    phone: str | None = None,
) -> Patient:
    """Register a patient and assign a privacy token."""
    token = f"{PRIVACY_TOKEN_PREFIX}-{secrets.token_hex(4).upper()}"
    patient_id = f"PT-{secrets.token_hex(4).upper()}"
    return Patient(
        patient_id=patient_id,
        privacy_token=token,
        name=name,
        age=age,
        gender=gender,
        village=village,
        phone=phone,
    )


def validate_vitals_tool(
    patient_id: str,
    blood_pressure: str,
    pulse: int,
    temperature: float,
    spo2: int,
    blood_glucose: float | None = None,
) -> VitalReading:
    """Record and triage patient vitals."""
    try:
        systolic = int(blood_pressure.split("/")[0])
    except (ValueError, IndexError):
        systolic = 0

    flag = spo2 < TRIAGE_CRITICAL_SPO2_THRESHOLD or systolic >= TRIAGE_CRITICAL_BP_SYSTOLIC

    return VitalReading(
        patient_id=patient_id,
        blood_pressure=blood_pressure,
        pulse=pulse,
        temperature=temperature,
        spo2=spo2,
        blood_glucose=blood_glucose,
        flag_triage=flag,
    )


def add_volunteer_tool(camp_id: str, name: str, role: str, shift: str) -> Volunteer:
    """Add a volunteer to a medical camp."""
    return Volunteer(
        volunteer_id=f"VOL-{secrets.token_hex(3).upper()}",
        name=name,
        role=role,
        shift=shift,
        is_confirmed=True,
    )


def generate_camp_summary_tool(
    camp_id: str,
    vitals: List[VitalReading],
    volunteers: List[Volunteer],
    medicines_dispensed: int,
    referrals_issued: int,
) -> CampSummary:
    """Produce an aggregate health summary for a completed camp."""
    total = len(vitals)
    critical = sum(1 for v in vitals if v.flag_triage)
    normal = sum(1 for v in vitals if not v.flag_triage and v.spo2 > 95)
    moderate = total - critical - normal
    completion = round(100.0 * total / max(total, 1), 1)
    return CampSummary(
        camp_id=camp_id,
        total_patients=total,
        triaged_critical=critical,
        triaged_moderate=moderate,
        triaged_normal=normal,
        volunteer_count=len(volunteers),
        medicines_dispensed=medicines_dispensed,
        referrals_issued=referrals_issued,
        completion_percentage=completion,
    )
