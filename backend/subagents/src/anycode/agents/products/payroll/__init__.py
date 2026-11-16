"""Payroll product package."""

from anycode.agents.products.payroll.agent import PayrollAgent
from anycode.agents.products.payroll.config import PayrollConfig, payroll_config
from anycode.agents.products.payroll.manifest import MANIFEST
from anycode.agents.products.payroll.schemas import (
    AnomalyReport,
    AttendanceRecord,
    DraftPayroll,
    PayslipSummary,
)

__all__ = [
    "PayrollAgent",
    "PayrollConfig",
    "payroll_config",
    "MANIFEST",
    "AttendanceRecord",
    "AnomalyReport",
    "DraftPayroll",
    "PayslipSummary",
]
