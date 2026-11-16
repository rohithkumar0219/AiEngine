"""Medical Camps manifest."""

from __future__ import annotations

MANIFEST = {
    "product_id": "iryax.medical_camps",
    "name": "Iryax Medical Camps",
    "version": "1.0.0",
    "description": (
        "[DEMO SANDBOX] Camp scheduling, volunteer roster management, patient check-in "
        "with privacy tokens, triage vital screening, and aggregate health summaries. "
        "Operates with simulated outreach records until live CAMP_API_URL is configured."
    ),
    "environment_mode": "demonstration_sandbox",
    "intents": [
        "plan_camp",
        "register_patient",
        "validate_vitals",
        "manage_volunteers",
        "camp_summary",
        "triage_patient",
        "medical_camp_overview",
    ],
    "required_roles": [
        "camp_coordinator",
        "health_worker",
        "doctor",
        "tenant_admin",
        "super_admin",
    ],
    "backend_service_env": "CAMP_API_URL",
}
