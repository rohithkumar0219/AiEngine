"""Coworking Space manifest."""

from __future__ import annotations

MANIFEST = {
    "product_id": "iryax.coworking",
    "name": "Iryax Coworking Space",
    "version": "1.0.0",
    "description": (
        "Seat availability and booking management, membership plans, invoice "
        "generation, refund approvals, and occupancy analytics."
    ),
    "intents": [
        "check_seat_availability",
        "book_seat",
        "cancel_booking",
        "generate_invoice",
        "process_refund",
        "occupancy_report",
        "manage_membership",
    ],
    "required_roles": [
        "coworking_member",
        "workspace_admin",
        "tenant_admin",
        "super_admin",
    ],
    "backend_service_env": "COWORKING_API_URL",
}
