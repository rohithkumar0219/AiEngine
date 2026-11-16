"""Payroll service layer."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List
from anycode.agents.products.payroll.config import payroll_config
from anycode.agents.products.payroll.schemas import (
    AnomalyReport,
    AttendanceRecord,
    DraftPayroll,
    PayslipSummary,
)


class PayrollService:
    """Calculations and reconciliation operations for Payroll & Attendance."""

    @property
    def is_backend_connected(self) -> bool:
        return payroll_config.is_backend_connected

    def reconcile(self, records: List[AttendanceRecord]) -> Dict[str, Any]:
        total_present = 0
        total_hours = 0.0
        anomalies: List[AnomalyReport] = []

        for r in records:
            if r.status == "present":
                total_present += 1
                total_hours += r.hours_worked

            if r.hours_worked > payroll_config.max_safe_daily_hours:
                anomalies.append(
                    AnomalyReport(
                        employee_id=r.employee_id,
                        employee_name=r.employee_name,
                        date=r.date,
                        anomaly_type="excessive_overtime",
                        severity="high",
                        details=f"Logged {r.hours_worked}h on {r.date}, exceeding threshold ({payroll_config.max_safe_daily_hours}h).",
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
                        details=f"Only {r.hours_worked}h logged on {r.date}. Potential missing check-out.",
                    )
                )

        return {
            "total_records_processed": len(records),
            "total_present_days": total_present,
            "total_hours_logged": round(total_hours, 2),
            "anomalies_detected": [a.model_dump() for a in anomalies],
        }

    def compute_draft(
        self,
        employee_id: str,
        employee_name: str,
        base_salary: float,
        days_present: int,
        overtime_hours: float = 0.0,
    ) -> DraftPayroll:
        days = payroll_config.standard_monthly_days
        daily_rate = base_salary / days if days > 0 else 0.0
        hourly_rate = daily_rate / 8.0 if daily_rate > 0 else 0.0

        prorated = round(daily_rate * min(days_present, days), 2)
        ot_pay = round(overtime_hours * hourly_rate * payroll_config.overtime_multiplier, 2)
        deductions = round(prorated * payroll_config.statutory_deduction_rate, 2)
        net = round(prorated + ot_pay - deductions, 2)

        return DraftPayroll(
            payroll_cycle=datetime.now(timezone.utc).strftime("%Y-%m"),
            employee_id=employee_id,
            employee_name=employee_name,
            base_salary=base_salary,
            overtime_pay=ot_pay,
            deductions=deductions,
            net_salary=net,
            total_days_present=days_present,
            total_days_leave=max(0, days - days_present),
            is_finalized=False,
            payment_status="draft_unpaid",
        )


payroll_service = PayrollService()
