"""OP Management Service and Backend Connector (Iryax OP Management)."""

from __future__ import annotations

import os
import uuid
from typing import Any, Dict, List, Optional

from iryax_platform.products.op_management.schemas import (
    AppointmentBooking,
    BillingSummary,
    DoctorAvailability,
    TokenQueueStatus,
)


class OPManagementService:
    """Operations for Outpatient Clinic doctor schedules, tokens, and billing calculation."""

    def __init__(self):
        self.api_url = os.getenv("OP_API_URL")
        self.api_key = os.getenv("OP_API_KEY")
        self._token_counters: Dict[str, int] = {}

    def is_backend_connected(self) -> bool:
        return bool(self.api_url and self.api_key)

    def check_doctor_availability(
        self,
        doctor_name_or_specialty: str,
        date: str = "Today",
    ) -> List[DoctorAvailability]:
        """Look up schedule for doctors by name or medical specialty."""
        doctors = [
            DoctorAvailability(
                doctor_id="doc_01",
                doctor_name="Dr. Ananya Reddy",
                specialty="Cardiology",
                available_date=date,
                available_slots=["09:30 AM", "10:30 AM", "11:30 AM", "03:00 PM"],
            ),
            DoctorAvailability(
                doctor_id="doc_02",
                doctor_name="Dr. Vikram Sen",
                specialty="General Medicine",
                available_date=date,
                available_slots=["10:00 AM", "11:00 AM", "02:00 PM", "04:30 PM"],
            ),
            DoctorAvailability(
                doctor_id="doc_03",
                doctor_name="Dr. Priya Nair",
                specialty="Pediatrics",
                available_date=date,
                available_slots=["09:00 AM", "10:00 AM", "01:30 PM"],
            ),
        ]

        q = doctor_name_or_specialty.lower()
        matches = [
            d for d in doctors
            if q in d.doctor_name.lower() or q in d.specialty.lower()
        ]
        return matches or doctors

    def book_appointment_token(
        self,
        patient_name: str,
        doctor_name: str,
        specialty: str,
        slot_time: str,
    ) -> AppointmentBooking:
        """Issue an OP appointment slot and queue token number."""
        key = f"{doctor_name}:{slot_time}"
        self._token_counters[key] = self._token_counters.get(key, 0) + 1
        token_num = self._token_counters[key]

        return AppointmentBooking(
            appointment_id=f"apt_{uuid.uuid4().hex[:8]}",
            patient_id=f"pt_{uuid.uuid4().hex[:6]}",
            patient_name=patient_name,
            doctor_name=doctor_name,
            specialty=specialty,
            slot_time=slot_time,
            token_number=token_num,
            status="confirmed",
        )

    def get_queue_status(self, doctor_name: str, department: str = "Outpatient") -> TokenQueueStatus:
        """Fetch current token queue progress and estimated wait duration."""
        return TokenQueueStatus(
            department=department,
            doctor_name=doctor_name,
            current_token_serving=12,
            total_tokens_issued=20,
            estimated_wait_minutes_per_token=10,
        )

    def calculate_billing_summary(
        self,
        patient_id: str,
        consultation_fee: float = 500.0,
        procedure_fees: float = 0.0,
        medication_estimate: float = 0.0,
    ) -> BillingSummary:
        """Compile outpatient consultation and service fees."""
        total = consultation_fee + procedure_fees + medication_estimate
        return BillingSummary(
            invoice_id=f"inv_op_{uuid.uuid4().hex[:8]}",
            patient_id=patient_id,
            consultation_fee=consultation_fee,
            procedure_fees=procedure_fees,
            medication_estimate=medication_estimate,
            total_amount=round(total, 2),
            payment_status="pending_at_billing_counter",
        )
