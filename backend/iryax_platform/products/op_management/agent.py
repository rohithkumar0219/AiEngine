"""OP Management Product Agent."""

from __future__ import annotations

from typing import Any, Dict, List

from iryax_platform.core.context import ProductId, Role
from iryax_platform.core.contracts import (
    AgentRequest,
    AgentResponse,
    ExecutionStatus,
    ToolCallRecord,
)
from iryax_platform.products.base import BaseProductAgent
from iryax_platform.products.op_management.schemas import AppointmentBooking
from iryax_platform.products.op_management.service import OPManagementService


class OPManagementAgent(BaseProductAgent):
    """Product Agent for Iryax Outpatient (OP) Clinic Management."""

    product_id = ProductId.OP_MANAGEMENT
    name = "Iryax OP Management Agent"
    description = (
        "Manages clinic doctor schedules, OP appointment booking, queue token issuance, "
        "wait time status, and outpatient billing calculations."
    )
    supported_intents = [
        "check_doctor_availability",
        "book_appointment",
        "get_queue_status",
        "calculate_billing",
        "general_op_query",
    ]
    required_roles = [Role.RECEPTIONIST, Role.DOCTOR, Role.TENANT_ADMIN]

    def __init__(self, service: OPManagementService | None = None):
        super().__init__()
        self.service = service or OPManagementService()
        self._register_default_tools()

    def _register_default_tools(self):
        self.register_tool("check_doctor_availability", self.service.check_doctor_availability)
        self.register_tool("book_appointment_token", self.service.book_appointment_token)
        self.register_tool("get_queue_status", self.service.get_queue_status)
        self.register_tool("calculate_billing_summary", self.service.calculate_billing_summary)

    def handle_request(self, request: AgentRequest) -> AgentResponse:
        query_lower = request.query.lower()
        tools_executed: List[ToolCallRecord] = []

        # 1. Clinical guardrail: Autonomous prescription modification or diagnosis
        if any(w in query_lower for w in ("prescribe", "change dosage", "modify prescription", "diagnose", "medical advice")):
            return AgentResponse(
                product_id=self.product_id,
                status=ExecutionStatus.PERMISSION_DENIED,
                response_text=(
                    "Clinical Safety Guardrail: Prescriptions and clinical diagnoses cannot be modified "
                    "or issued by AI. Please consult the attending doctor during your scheduled OP consultation."
                ),
                tools_executed=[],
            )

        # 2. Check doctor availability
        if any(w in query_lower for w in ("doctor", "available", "schedule", "specialist", "timings")):
            doc_query = request.parameters.get("doctor_or_specialty", request.query)
            date = request.parameters.get("date", "Today")

            call_record = self.execute_tool(
                "check_doctor_availability",
                {"doctor_name_or_specialty": doc_query, "date": date},
                request.context,
            )
            tools_executed.append(call_record)
            results = call_record.output

            docs_desc = "; ".join([f"{d.doctor_name} ({d.specialty}): Slots {', '.join(d.available_slots)}" for d in results])
            return AgentResponse(
                product_id=self.product_id,
                status=ExecutionStatus.SUCCESS,
                response_text=f"Found {len(results)} doctor schedule(s) for {date}: {docs_desc}",
                structured_data={"doctors": [d.model_dump() for d in results]},
                tools_executed=tools_executed,
            )

        # 3. Book appointment and issue token
        if any(w in query_lower for w in ("book appointment", "take token", "appointment", "reserve slot")):
            patient_name = request.parameters.get("patient_name", "Patient")
            doctor_name = request.parameters.get("doctor_name", "Dr. Vikram Sen")
            specialty = request.parameters.get("specialty", "General Medicine")
            slot = request.parameters.get("slot_time", "10:00 AM")

            call_record = self.execute_tool(
                "book_appointment_token",
                {
                    "patient_name": patient_name,
                    "doctor_name": doctor_name,
                    "specialty": specialty,
                    "slot_time": slot,
                },
                request.context,
            )
            tools_executed.append(call_record)
            booking: AppointmentBooking = call_record.output

            return AgentResponse(
                product_id=self.product_id,
                status=ExecutionStatus.SUCCESS,
                response_text=(
                    f"Appointment confirmed for {patient_name} with {doctor_name} ({specialty}) "
                    f"at {slot}. Your OP Queue Token number is #{booking.token_number} (Appointment ID: {booking.appointment_id})."
                ),
                structured_data=booking.model_dump(),
                tools_executed=tools_executed,
            )

        # 4. Token Queue status
        if any(w in query_lower for w in ("queue", "token status", "wait time", "now serving")):
            doctor_name = request.parameters.get("doctor_name", "Dr. Vikram Sen")
            call_record = self.execute_tool("get_queue_status", {"doctor_name": doctor_name}, request.context)
            tools_executed.append(call_record)
            q_status = call_record.output

            wait = (q_status.total_tokens_issued - q_status.current_token_serving) * q_status.estimated_wait_minutes_per_token
            return AgentResponse(
                product_id=self.product_id,
                status=ExecutionStatus.SUCCESS,
                response_text=(
                    f"Token Queue for {doctor_name}: Currently serving Token #{q_status.current_token_serving}. "
                    f"Total tokens issued: {q_status.total_tokens_issued}. Estimated wait for new tokens: ~{wait} minutes."
                ),
                structured_data=q_status.model_dump(),
                tools_executed=tools_executed,
            )

        # 5. Check live backend sync
        if "sync" in query_lower or "op api" in query_lower:
            if not self.service.is_backend_connected():
                return AgentResponse(
                    product_id=self.product_id,
                    status=ExecutionStatus.BLOCKED_BACKEND,
                    response_text=(
                        "Live Iryax OP Management backend service is not configured in this environment "
                        "(missing OP_API_URL). Local scheduling, token generation, and billing calculations remain operational."
                    ),
                    backend_supported=False,
                    missing_backend_message="Missing OP_API_URL",
                )

        # 6. Default
        return AgentResponse(
            product_id=self.product_id,
            status=ExecutionStatus.SUCCESS,
            response_text=(
                "Iryax OP Management Agent is ready. You can query doctor availability, schedule appointments, "
                "issue queue tokens, check current waiting times, or calculate consultation billing."
            ),
            tools_executed=[],
        )
