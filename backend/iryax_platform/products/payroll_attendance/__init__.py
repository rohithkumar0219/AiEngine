"""Attendance and Payroll product agent package."""

from iryax_platform.products.payroll_attendance.agent import AttendancePayrollAgent
from iryax_platform.products.payroll_attendance.schemas import (
    AnomalyReport,
    AttendanceRecord,
    DraftPayroll,
    LeaveOvertimeRequest,
    PayslipSummary,
)
from iryax_platform.products.payroll_attendance.service import AttendancePayrollService

__all__ = [
    "AttendancePayrollAgent",
    "AnomalyReport",
    "AttendanceRecord",
    "DraftPayroll",
    "LeaveOvertimeRequest",
    "PayslipSummary",
    "AttendancePayrollService",
]
