"""Lab Management manifest."""

from __future__ import annotations

MANIFEST = {
    "product_id": "iryax.lab_management",
    "name": "Iryax Lab Management",
    "version": "1.0.0",
    "description": (
        "Laboratory order management, sample tracking, result entry, "
        "pathologist-gated report release, and aggregate lab analytics."
    ),
    "intents": [
        "create_lab_order",
        "register_sample",
        "enter_results",
        "release_report",
        "track_sample",
        "lab_analytics",
        "flag_abnormal_results",
    ],
    "required_roles": [
        "lab_technician",
        "pathologist",
        "doctor",
        "tenant_admin",
        "super_admin",
    ],
    "backend_service_env": "LAB_API_URL",
}
