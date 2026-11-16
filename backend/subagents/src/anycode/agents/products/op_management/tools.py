"""OP Management domain tools."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone

from anycode.agents.products.op_management.config import (
    DEFAULT_SLOT_DURATION_MINUTES,
    TOKEN_COUNTER_PREFIX,
)
from anycode.agents.products.op_management.schemas import (
    Appointment,
    DoctorSchedule,
    OPSummary,
    Token,
)


def book_appointment_tool(
    patient_id: str,
    doctor_id: str,
    department: str,
    slot_time: str,
) -> Appointment:
    """Create a new outpatient appointment."""
    return Appointment(
        appointment_id=f"APT-{secrets.token_hex(4).upper()}",
        patient_id=patient_id,
        doctor_id=doctor_id,
        department=department,
        slot_time=slot_time,
        status="scheduled",
    )


def cancel_appointment_tool(appointment: Appointment, reason: str = "") -> Appointment:
    """Cancel an existing appointment."""
    appointment.status = "cancelled"
    appointment.notes = f"Cancelled: {reason}" if reason else "Cancelled"
    return appointment


def issue_token_tool(appointment: Appointment, token_number: int, counter: str) -> Token:
    """Issue a queue token after patient check-in."""
    wait_estimate = token_number * DEFAULT_SLOT_DURATION_MINUTES
    appointment.status = "checked_in"
    appointment.token_number = token_number
    return Token(
        token_id=f"{TOKEN_COUNTER_PREFIX}-{secrets.token_hex(3).upper()}",
        appointment_id=appointment.appointment_id,
        token_number=token_number,
        issued_at=datetime.now(timezone.utc).isoformat(),
        estimated_wait_minutes=wait_estimate,
        counter=counter,
    )


def check_doctor_availability_tool(schedule: DoctorSchedule, requested_slot: str) -> bool:
    """Return True if a slot is available for the doctor."""
    return (
        requested_slot in schedule.available_slots
        and requested_slot not in schedule.booked_slots
        and len(schedule.booked_slots) < schedule.max_daily_patients
    )


def generate_op_summary_tool(
    date: str,
    appointments: list[Appointment],
) -> OPSummary:
    """Produce a daily OP clinic summary."""
    completed = sum(1 for a in appointments if a.status == "completed")
    cancelled = sum(1 for a in appointments if a.status == "cancelled")
    waiting = sum(1 for a in appointments if a.status in ("scheduled", "checked_in"))
    departments = list({a.department for a in appointments})
    avg_wait = float(DEFAULT_SLOT_DURATION_MINUTES * max(waiting, 1))
    return OPSummary(
        date=date,
        total_appointments=len(appointments),
        completed=completed,
        cancelled=cancelled,
        waiting=waiting,
        average_wait_minutes=avg_wait,
        departments=departments,
    )
