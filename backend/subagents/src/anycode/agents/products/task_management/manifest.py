"""Task Management product manifest."""

from __future__ import annotations

MANIFEST = {
    "product_id": "iryax.task_management",
    "name": "Iryax Task Management",
    "version": "1.0.0",
    "description": "Task creation, decomposition, dependency tracking, blocker detection, and project progress summaries.",
    "intents": [
        "create_task",
        "decompose_task",
        "detect_blockers",
        "summarize_project",
        "bulk_modify_tasks",
        "task_overview",
    ],
    "required_roles": ["task_lead", "employee", "tenant_admin", "super_admin"],
    "backend_service_env": "TASKMANAGEMENT_API_URL",
}
