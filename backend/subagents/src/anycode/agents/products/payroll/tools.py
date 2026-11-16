"""Payroll tools implementations."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List
from anycode.agents.products.payroll.schemas import AttendanceRecord, DraftPayroll, PayslipSummary
from anycode.agents.products.payroll.services import payroll_service


def reconcile_attendance_tool(records: List[AttendanceRecord]) -> Dict[str, Any]:
    return payroll_service.reconcile(records)


def calculate_draft_payroll_tool(
    employee_id: str,
    employee_name: str,
    base_salary: float,
    days_present: int,
    overtime_hours: float = 0.0,
) -> DraftPayroll:
    return payroll_service.compute_draft(employee_id, employee_name, base_salary, days_present, overtime_hours)


def generate_payslip_tool(draft: DraftPayroll) -> PayslipSummary:
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
