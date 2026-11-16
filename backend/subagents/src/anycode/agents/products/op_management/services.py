"""OP Management services — domain business logic."""

from __future__ import annotations

from typing import List

from anycode.agents.products.op_management.schemas import Appointment, DoctorSchedule


class AppointmentService:
    """Manages appointment lifecycle and slot logic."""

    def get_next_token(self, appointments: List[Appointment]) -> int:
        checked_in = [a for a in appointments if a.token_number is not None]
        return max((a.token_number for a in checked_in), default=0) + 1

    def complete_appointment(self, appointment: Appointment) -> Appointment:
        appointment.status = "completed"
        return appointment


class ScheduleService:
    """Doctor availability and schedule management."""

    def get_free_slots(self, schedule: DoctorSchedule) -> List[str]:
        return [
            s for s in schedule.available_slots if s not in schedule.booked_slots
        ]

    def book_slot(self, schedule: DoctorSchedule, slot: str) -> bool:
        if slot not in schedule.available_slots or slot in schedule.booked_slots:
            return False
        schedule.booked_slots.append(slot)
        return True
