"""Medical Camps services — domain business logic."""

from __future__ import annotations

from typing import List

from anycode.agents.products.medical_camps.schemas import MedicalCamp, Patient, VitalReading


class CampService:
    """Manages camp lifecycle: creation, activation, closure."""

    def activate_camp(self, camp: MedicalCamp) -> MedicalCamp:
        if camp.status != "planned":
            raise ValueError(f"Camp {camp.camp_id} is not in 'planned' state.")
        camp.status = "active"
        return camp

    def close_camp(self, camp: MedicalCamp) -> MedicalCamp:
        if camp.status != "active":
            raise ValueError(f"Camp {camp.camp_id} is not active.")
        camp.status = "completed"
        return camp


class PatientService:
    """Patient registration and privacy-token management."""

    def lookup_by_token(
        self, token: str, registry: List[Patient]
    ) -> Patient | None:
        return next((p for p in registry if p.privacy_token == token), None)

    def triage_category(self, vitals: VitalReading) -> str:
        if vitals.flag_triage:
            return "critical"
        if vitals.spo2 <= 95:
            return "moderate"
        return "normal"
