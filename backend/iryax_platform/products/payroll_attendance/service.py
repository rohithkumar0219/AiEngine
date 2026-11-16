"""Attendance and Payroll Service and Backend Connector (TimelyHealth / Iryax Payroll)."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from iryax_platform.core.audit import approval_store
from iryax_platform.core.context import Role, TenantContext
from iryax_platform.core.contracts import ApprovalRequest
from iryax_platform.products.payroll_attendance.schemas import (
    AnomalyReport,
    AttendanceRecord,
    DraftPayroll,
    LeaveOvertimeRequest,
    PayslipSummary,
)


class AttendancePayrollService:
    """Business operations and calculations for attendance reconciliation & payroll draft."""

    def __init__(self):
        self.api_url = os.getenv("TIMELYHEALTH_API_URL")
        self.api_key = os.getenv("TIMELYHEALTH_API_KEY")

    def is_backend_connected(self) -> bool:
        return bool(self.api_url and self.api_key)

    def reconcile_attendance(
        self,
        records: List[AttendanceRecord],
    ) -> Dict[str, Any]:
        """Reconcile attendance records, calculate total hours, and detect punch discrepancies."""
        total_present = 0
        total_hours = 0.0
        anomalies: List[AnomalyReport] = []

        for r in records:
            if r.status == "present":
                total_present += 1
                total_hours += r.hours_worked

            # Detect missing punch or unusual hours
            if r.hours_worked > 14.0:
                anomalies.append(
                    AnomalyReport(
                        employee_id=r.employee_id,
                        employee_name=r.employee_name,
                        date=r.date,
                        anomaly_type="excessive_overtime",
                        severity="high",
                        details=f"Worked {r.hours_worked} hours on {r.date}, exceeding standard safety limit of 14 hours.",
                    )
                )
            elif r.hours_worked < 4.0 and r.status == "present":
                anomalies.append(
                    AnomalyReport(
                        employee_id=r.employee_id,
                        employee_name=r.employee_name,
                        date=r.date,
                        anomaly_type="missing_punch",
                        severity="medium",
                        details=f"Only {r.hours_worked} hours logged on {r.date}. Possible missing check-out punch.",
                    )
                )

        return {
            "total_records_processed": len(records),
            "total_present_days": total_present,
            "total_hours_logged": round(total_hours, 2),
            "anomalies_detected": [a.model_dump() for a in anomalies],
        }

    def calculate_draft_payroll(
        self,
        employee_id: str,
        employee_name: str,
        base_salary: float,
        days_present: int,
        standard_working_days: int = 22,
        overtime_hours: float = 0.0,
    ) -> DraftPayroll:
        """Calculate draft payroll components according to standard formula."""
        daily_rate = base_salary / standard_working_days if standard_working_days > 0 else 0.0
        hourly_rate = daily_rate / 8.0 if daily_rate > 0 else 0.0

        prorated_salary = round(daily_rate * min(days_present, standard_working_days), 2)
        overtime_pay = round(overtime_hours * hourly_rate * 1.5, 2)
        deductions = round(prorated_salary * 0.12, 2)  # E.g., PF / tax deduction
        net_salary = round(prorated_salary + overtime_pay - deductions, 2)

        return DraftPayroll(
            payroll_cycle=datetime.now(timezone.utc).strftime("%Y-%m"),
            employee_id=employee_id,
            employee_name=employee_name,
            base_salary=base_salary,
            overtime_pay=overtime_pay,
            deductions=deductions,
            net_salary=net_salary,
            total_days_present=days_present,
            total_days_leave=max(0, standard_working_days - days_present),
            is_finalized=False,
            payment_status="draft_unpaid",
        )

    def generate_payslip(self, draft: DraftPayroll) -> PayslipSummary:
        """Generate a draft payslip summary from payroll calculations."""
        return PayslipSummary(
            payslip_id=f"pay_{uuid.uuid4().hex[:8]}",
            employee_id=draft.employee_id,
            employee_name=draft.employee_name,
            cycle=draft.payroll_cycle,
            gross_pay=round(draft.base_salary + draft.overtime_pay, 2),
            deductions=draft.deductions,
            net_pay=draft.net_salary,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    def create_payment_release_approval(
        self,
        context: TenantContext,
        cycle: str,
        total_amount: float,
        recipient_count: int,
    ) -> ApprovalRequest:
        """Create Human-In-The-Loop approval request to authorize payroll release."""
        return approval_store.create_request(
            tenant_id=context.tenant_id,
            product_id="iryax.attendance_payroll",
            operation_name="release_payment",
            payload={
                "cycle": cycle,
                "total_amount": total_amount,
                "recipient_count": recipient_count,
                "requested_by": context.user_id,
            },
            required_roles=[Role.SUPER_ADMIN, Role.PAYROLL_ADMIN],
        )
