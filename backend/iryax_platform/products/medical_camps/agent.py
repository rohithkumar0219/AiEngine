"""Medical Camps Product Agent."""

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
from iryax_platform.products.medical_camps.schemas import VitalValidation
from iryax_platform.products.medical_camps.service import MedicalCampsService


class MedicalCampsAgent(BaseProductAgent):
    """Product Agent for Iryax Medical Camps (planning, triage vital checks, reporting)."""

    product_id = ProductId.MEDICAL_CAMPS
    name = "Iryax Medical Camps Agent"
    description = (
        "Coordinates medical camp scheduling, volunteer management, patient check-in, "
        "triage vital measurement validation (non-diagnostic), and aggregate reporting."
    )
    supported_intents = [
        "plan_camp",
        "register_patient",
        "validate_vitals",
        "camp_summary",
        "general_camp_query",
    ]
    required_roles = [Role.CAMP_COORDINATOR, Role.HEALTH_WORKER, Role.DOCTOR, Role.TENANT_ADMIN]

    def __init__(self, service: MedicalCampsService | None = None):
        super().__init__()
        self.service = service or MedicalCampsService()
        self._register_default_tools()

    def _register_default_tools(self):
        self.register_tool("plan_camp", self.service.plan_camp)
        self.register_tool("register_patient", self.service.register_patient)
        self.register_tool("validate_vitals", self.service.validate_vitals)
        self.register_tool("generate_camp_summary", self.service.generate_camp_summary)

    def handle_request(self, request: AgentRequest) -> AgentResponse:
        query_lower = request.query.lower()
        tools_executed: List[ToolCallRecord] = []

        # 1. Clinical guardrail: Autonomous diagnosis or prescription
        if any(w in query_lower for w in ("diagnose", "prescribe", "treatment for", "what disease", "cure")):
            return AgentResponse(
                product_id=self.product_id,
                status=ExecutionStatus.PERMISSION_DENIED,
                response_text=(
                    "Clinical Safety Guardrail: AI systems are strictly prohibited from diagnosing patients "
                    "or prescribing medical treatments. Patient symptoms and vital measurements must be directly "
                    "examined by a licensed medical practitioner on-site."
                ),
                tools_executed=[],
            )

        # 2. Vital measurement validation (statistical triage screening)
        if any(w in query_lower for w in ("vital", "bp", "blood pressure", "pulse", "glucose", "triage")):
            token = request.parameters.get("patient_token", "PT-DEMO01")
            sbp = int(request.parameters.get("systolic_bp", 120))
            dbp = int(request.parameters.get("diastolic_bp", 80))
            pulse = int(request.parameters.get("pulse_rate", 72))
            glucose = request.parameters.get("glucose_mg_dl")
            if glucose is not None:
                glucose = float(glucose)

            call_record = self.execute_tool(
                "validate_vitals",
                {
                    "patient_token": token,
                    "systolic_bp": sbp,
                    "diastolic_bp": dbp,
                    "pulse_rate": pulse,
                    "glucose_mg_dl": glucose,
                },
                request.context,
            )
            tools_executed.append(call_record)
            vitals: VitalValidation = call_record.output

            status_str = "Within expected statistical ranges." if not vitals.is_abnormal else (
                f"Flagged {len(vitals.flagged_reasons)} item(s): {', '.join(vitals.flagged_reasons)}."
            )

            return AgentResponse(
                product_id=self.product_id,
                status=ExecutionStatus.SUCCESS,
                response_text=(
                    f"Validated triage measurements for token {vitals.patient_token}: {status_str} "
                    f"Notice: {vitals.clinical_disclaimer}"
                ),
                structured_data=vitals.model_dump(),
                tools_executed=tools_executed,
            )

        # 3. Plan medical camp
        if any(w in query_lower for w in ("plan camp", "organize camp", "schedule camp", "new camp")):
            name = request.parameters.get("camp_name", "Rural Health Outreach Camp")
            loc = request.parameters.get("location", "Community Center")
            date = request.parameters.get("target_date", "2026-11-15")
            expected = int(request.parameters.get("expected_attendees", 150))

            call_record = self.execute_tool(
                "plan_camp",
                {
                    "camp_name": name,
                    "location": loc,
                    "target_date": date,
                    "expected_attendees": expected,
                },
                request.context,
            )
            tools_executed.append(call_record)
            plan = call_record.output

            return AgentResponse(
                product_id=self.product_id,
                status=ExecutionStatus.SUCCESS,
                response_text=(
                    f"Created camp schedule for '{plan.camp_name}' at {plan.location} on {plan.target_date}. "
                    f"Capacity: {plan.expected_attendees} patients. Camp ID: {plan.camp_id}."
                ),
                structured_data=plan.model_dump(),
                tools_executed=tools_executed,
            )

        # 4. Check live backend sync
        if "sync" in query_lower or "camp api" in query_lower:
            if not self.service.is_backend_connected():
                return AgentResponse(
                    product_id=self.product_id,
                    status=ExecutionStatus.BLOCKED_BACKEND,
                    response_text=(
                        "Live Iryax Medical Camps backend service is not configured in this environment "
                        "(missing CAMP_API_URL). Local planning, volunteer manifests, and vital checks remain operational."
                    ),
                    backend_supported=False,
                    missing_backend_message="Missing CAMP_API_URL",
                )

        # 5. Default
        return AgentResponse(
            product_id=self.product_id,
            status=ExecutionStatus.SUCCESS,
            response_text=(
                "Iryax Medical Camps Agent is ready. You can schedule camps, register patients under privacy tokens, "
                "validate triage vital readings, or generate non-identifying aggregate camp summaries."
            ),
            tools_executed=[],
        )
