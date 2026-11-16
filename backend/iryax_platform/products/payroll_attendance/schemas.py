"""Typed schemas for Attendance and Payroll Agent."""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class AttendanceRecord(BaseModel):
    employee_id: str
    employee_name: str
    date: str
    check_in: str
    check_out: str
    hours_worked: float
    status: str = "present"  # present, absent, half_day, leave
    anomaly_detected: bool = False
    anomaly_notes: Optional[str] = None


class LeaveOvertimeRequest(BaseModel):
    employee_id: str
    request_type: str  # leave, overtime
    start_date: str
    end_date: str
    hours: float = 0.0
    reason: str
    is_approved: bool = False


class AnomalyReport(BaseModel):
    employee_id: str
    employee_name: str
    date: str
    anomaly_type: str  # excessive_overtime, missing_punch, sudden_absenteeism
    severity: str  # low, medium, high
    details: str


class DraftPayroll(BaseModel):
    payroll_cycle: str  # e.g., '2026-10'
    employee_id: str
    employee_name: str
    base_salary: float
    overtime_pay: float = 0.0
    deductions: float = 0.0
    net_salary: float
    total_days_present: int
    total_days_leave: int
    is_finalized: bool = False
    payment_status: str = "draft_unpaid"


class PayslipSummary(BaseModel):
    payslip_id: str
    employee_id: str
    employee_name: str
    cycle: str
    gross_pay: float
    deductions: float
    net_pay: float
    generated_at: str
