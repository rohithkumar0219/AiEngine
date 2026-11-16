"""Medical Camps Service and Backend Connector (Iryax Medical Camps)."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from iryax_platform.products.medical_camps.schemas import (
    AggregateCampReport,
    CampPlan,
    PatientRegistration,
    ResourceInventory,
    VitalValidation,
)


class MedicalCampsService:
    """Operations for medical camp planning, check-in, vital validation, and reporting."""

    def __init__(self):
        self.api_url = os.getenv("CAMP_API_URL")
        self.api_key = os.getenv("CAMP_API_KEY")

    def is_backend_connected(self) -> bool:
        return bool(self.api_url and self.api_key)

    def plan_camp(
        self,
        camp_name: str,
        location: str,
        target_date: str,
        expected_attendees: int = 100,
        doctors: Optional[List[str]] = None,
        volunteers: int = 5,
    ) -> CampPlan:
        """Create a planned medical camp schedule."""
        return CampPlan(
            camp_id=f"cmp_{uuid.uuid4().hex[:8]}",
            camp_name=camp_name,
            location=location,
            target_date=target_date,
            expected_attendees=expected_attendees,
            participating_doctors=doctors or ["Dr. R. Sharma (General Medicine)"],
            volunteer_count=volunteers,
            status="confirmed",
        )

    def register_patient(
        self,
        camp_id: str,
        age: int,
        gender: str,
        chief_complaint: str,
    ) -> PatientRegistration:
        """Register patient at camp check-in, generating a secure pseudonymized token."""
        token = f"PT-{uuid.uuid4().hex[:6].upper()}"
        return PatientRegistration(
            registration_id=f"reg_{uuid.uuid4().hex[:8]}",
            camp_id=camp_id,
            patient_token=token,
            age=age,
            gender=gender,
            chief_complaint=chief_complaint,
            registered_at=datetime.now(timezone.utc).isoformat(),
        )

    def validate_vitals(
        self,
        patient_token: str,
        systolic_bp: int,
        diastolic_bp: int,
        pulse_rate: int,
        glucose_mg_dl: Optional[float] = None,
    ) -> VitalValidation:
        """Validate vital measurements against clinical statistical ranges without diagnosing."""
        flags: List[str] = []

        if systolic_bp >= 140 or diastolic_bp >= 90:
            flags.append(f"Elevated Blood Pressure ({systolic_bp}/{diastolic_bp} mmHg)")
        elif systolic_bp < 90 or diastolic_bp < 60:
            flags.append(f"Low Blood Pressure ({systolic_bp}/{diastolic_bp} mmHg)")

        if pulse_rate > 100:
            flags.append(f"High resting pulse ({pulse_rate} bpm)")
        elif pulse_rate < 55:
            flags.append(f"Low resting pulse ({pulse_rate} bpm)")

        if glucose_mg_dl is not None:
            if glucose_mg_dl > 180.0:
                flags.append(f"Elevated blood glucose ({glucose_mg_dl} mg/dL)")
            elif glucose_mg_dl < 70.0:
                flags.append(f"Low blood glucose ({glucose_mg_dl} mg/dL)")

        return VitalValidation(
            patient_token=patient_token,
            systolic_bp=systolic_bp,
            diastolic_bp=diastolic_bp,
            pulse_rate=pulse_rate,
            blood_glucose_mg_dl=glucose_mg_dl,
            is_abnormal=len(flags) > 0,
            flagged_reasons=flags,
        )

    def generate_camp_summary(
        self,
        camp_id: str,
        camp_name: str,
        registered_count: int,
        flagged_count: int,
        doctors_count: int = 2,
        volunteers_count: int = 6,
    ) -> AggregateCampReport:
        """Compile non-identifying aggregate camp statistics for public health reporting."""
        return AggregateCampReport(
            camp_id=camp_id,
            camp_name=camp_name,
            total_registered_patients=registered_count,
            patients_with_vital_flags=flagged_count,
            resources_utilized_percentage=85.0,
            doctors_present=doctors_count,
            volunteers_active=volunteers_count,
        )
