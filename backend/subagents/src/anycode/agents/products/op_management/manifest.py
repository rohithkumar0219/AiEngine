"""OP Management manifest."""

from __future__ import annotations

MANIFEST = {
    "product_id": "iryax.op_management",
    "name": "Iryax OP Management",
    "version": "1.0.0",
    "description": (
        "Outpatient clinic management — appointment scheduling, token "
        "queue management, doctor schedule visibility, and daily OP summaries."
    ),
    "intents": [
        "book_appointment",
        "cancel_appointment",
        "reschedule_appointment",
        "issue_token",
        "check_doctor_availability",
        "op_daily_summary",
        "patient_check_in",
    ],
    "required_roles": [
        "receptionist",
        "doctor",
        "health_worker",
        "tenant_admin",
        "super_admin",
    ],
    "backend_service_env": "OP_API_URL",
}
