"""Payroll and attendance product manifest."""

from __future__ import annotations

MANIFEST = {
    "product_id": "iryax.payroll",
    "name": "Iryax Attendance and Payroll",
    "version": "1.0.0",
    "description": "Attendance reconciliation, overtime calculation, draft payroll, payslip generation, and payment release approvals.",
    "intents": [
        "reconcile_attendance",
        "calculate_payroll",
        "generate_payslip",
        "detect_anomalies",
        "release_payment",
        "payroll_overview",
    ],
    "required_roles": ["payroll_admin", "hr_admin", "tenant_admin", "super_admin", "employee"],
    "backend_service_env": "TIMELYHEALTH_API_URL",
}
