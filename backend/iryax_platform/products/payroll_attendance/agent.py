"""Attendance and Payroll Product Agent."""

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
from iryax_platform.products.payroll_attendance.schemas import AttendanceRecord
from iryax_platform.products.payroll_attendance.service import AttendancePayrollService


class AttendancePayrollAgent(BaseProductAgent):
    """Product Agent for Iryax Attendance & Payroll."""

    product_id = ProductId.ATTENDANCE_PAYROLL
    name = "Iryax Attendance & Payroll Agent"
    description = (
        "Handles attendance reconciliation, overtime and leave validation, "
        "draft payroll computation, anomaly detection, and payslip generation."
    )
    supported_intents = [
        "reconcile_attendance",
        "calculate_payroll",
        "generate_payslip",
        "detect_anomalies",
        "release_payment",
        "general_payroll_query",
    ]
    required_roles = [Role.HR_ADMIN, Role.PAYROLL_ADMIN, Role.EMPLOYEE, Role.TENANT_ADMIN]

    def __init__(self, service: AttendancePayrollService | None = None):
        super().__init__()
        self.service = service or AttendancePayrollService()
        self._register_default_tools()

    def _register_default_tools(self):
        self.register_tool("reconcile_attendance", self.service.reconcile_attendance)
        self.register_tool("calculate_draft_payroll", self.service.calculate_draft_payroll)
        self.register_tool("generate_payslip", self.service.generate_payslip)
        self.register_tool("create_payment_release_approval", self.service.create_payment_release_approval)

    def handle_request(self, request: AgentRequest) -> AgentResponse:
        query_lower = request.query.lower()
        tools_executed: List[ToolCallRecord] = []

        # 1. Guardrail: Payment release or modifying sensitive bank/salary details
        if any(w in query_lower for w in ("release payment", "disburse salary", "payout", "send money", "execute payroll")):
            cycle = request.parameters.get("cycle", "Current Cycle")
            total_amt = float(request.parameters.get("total_amount", 500000.0))
            count = int(request.parameters.get("recipient_count", 15))

            call_record = self.execute_tool(
                "create_payment_release_approval",
                {
                    "context": request.context,
                    "cycle": cycle,
                    "total_amount": total_amt,
                    "recipient_count": count,
                },
                request.context,
            )
            tools_executed.append(call_record)
            approval_req = call_record.output

            return AgentResponse(
                product_id=self.product_id,
                status=ExecutionStatus.PENDING_APPROVAL,
                response_text=(
                    f"Security policy strictly forbids autonomous disbursement of employee funds. "
                    f"A disbursement approval request (ID: {approval_req.approval_id}) has been created "
                    f"for {cycle} totaling INR {total_amt:,.2f} across {count} employees. "
                    f"Authorized Payroll Admin approval is required before funds are released."
                ),
                structured_data={"approval_id": approval_req.approval_id, "status": "pending_approval"},
                tools_executed=tools_executed,
                approval_request=approval_req,
            )

        # 2. Reconcile attendance
        if any(w in query_lower for w in ("attendance", "punch", "hours", "overtime", "reconcile")):
            records_raw = request.parameters.get("records", [])
            records: List[AttendanceRecord] = []
            if isinstance(records_raw, list) and records_raw:
                for r in records_raw:
                    if isinstance(r, dict):
                        records.append(AttendanceRecord(**r))
            else:
                # Default sample record for testing reconciliation
                records = [
                    AttendanceRecord(
                        employee_id="EMP001",
                        employee_name="John Doe",
                        date="2026-10-01",
                        check_in="09:00",
                        check_out="18:00",
                        hours_worked=9.0,
                    ),
                    AttendanceRecord(
                        employee_id="EMP002",
                        employee_name="Jane Smith",
                        date="2026-10-01",
                        check_in="09:00",
                        check_out="23:30",
                        hours_worked=14.5,
                    ),
                ]

            call_record = self.execute_tool("reconcile_attendance", {"records": records}, request.context)
            tools_executed.append(call_record)
            result = call_record.output

            return AgentResponse(
                product_id=self.product_id,
                status=ExecutionStatus.SUCCESS,
                response_text=(
                    f"Reconciled {result['total_records_processed']} attendance records. "
                    f"Logged {result['total_hours_logged']} total hours. "
                    f"Detected {len(result['anomalies_detected'])} potential attendance anomalies."
                ),
                structured_data=result,
                tools_executed=tools_executed,
            )

        # 3. Draft payroll calculation
        if any(w in query_lower for w in ("payroll", "salary", "payslip", "calculate pay")):
            emp_id = request.parameters.get("employee_id", "EMP001")
            emp_name = request.parameters.get("employee_name", "Employee")
            base = float(request.parameters.get("base_salary", 60000.0))
            present = int(request.parameters.get("days_present", 21))
            ot = float(request.parameters.get("overtime_hours", 4.0))

            call_record = self.execute_tool(
                "calculate_draft_payroll",
                {
                    "employee_id": emp_id,
                    "employee_name": emp_name,
                    "base_salary": base,
                    "days_present": present,
                    "overtime_hours": ot,
                },
                request.context,
            )
            tools_executed.append(call_record)
            draft = call_record.output

            payslip_call = self.execute_tool("generate_payslip", {"draft": draft}, request.context)
            tools_executed.append(payslip_call)
            payslip = payslip_call.output

            return AgentResponse(
                product_id=self.product_id,
                status=ExecutionStatus.SUCCESS,
                response_text=(
                    f"Calculated draft payroll for {emp_name} ({emp_id}). "
                    f"Gross: INR {payslip.gross_pay:,.2f}, Deductions: INR {payslip.deductions:,.2f}, "
                    f"Net Payable: INR {payslip.net_pay:,.2f}. Payslip generated: {payslip.payslip_id}."
                ),
                structured_data={
                    "payroll": draft.model_dump(),
                    "payslip": payslip.model_dump(),
                },
                tools_executed=tools_executed,
            )

        # 4. Check live backend sync
        if "sync" in query_lower or "timelyhealth" in query_lower:
            if not self.service.is_backend_connected():
                return AgentResponse(
                    product_id=self.product_id,
                    status=ExecutionStatus.BLOCKED_BACKEND,
                    response_text=(
                        "Live TimelyHealth payroll/attendance backend is not configured in this environment "
                        "(missing TIMELYHEALTH_API_URL). Offline calculations and policy enforcement remain operational."
                    ),
                    backend_supported=False,
                    missing_backend_message="Missing TIMELYHEALTH_API_URL",
                )

        # 5. Default
        return AgentResponse(
            product_id=self.product_id,
            status=ExecutionStatus.SUCCESS,
            response_text=(
                "Iryax Attendance & Payroll Agent is ready. "
                "You can reconcile attendance records, detect punch anomalies, calculate draft payroll, "
                "or request payment release approvals."
            ),
            tools_executed=[],
        )
