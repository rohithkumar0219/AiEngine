"""Task Management Service and Backend Connector (Iryax Task Management)."""

from __future__ import annotations

import os
import uuid
from typing import Any, Dict, List, Optional

from iryax_platform.core.audit import approval_store
from iryax_platform.core.context import Role, TenantContext
from iryax_platform.core.contracts import ApprovalRequest
from iryax_platform.products.task_management.schemas import (
    BlockerReport,
    ProjectSummary,
    TaskDecomposition,
    TaskItem,
)


class TaskManagementService:
    """Business operations for task creation, decomposition, dependency tracking, and blocker analysis."""

    def __init__(self):
        self.api_url = os.getenv("TASKMANAGEMENT_API_URL")
        self.api_key = os.getenv("TASKMANAGEMENT_API_KEY")

    def is_backend_connected(self) -> bool:
        return bool(self.api_url and self.api_key)

    def create_task(
        self,
        title: str,
        description: str,
        assigned_to: Optional[str] = None,
        priority: str = "medium",
        due_date: Optional[str] = None,
        dependencies: Optional[List[str]] = None,
    ) -> TaskItem:
        """Create a new tracked task."""
        return TaskItem(
            task_id=f"tsk_{uuid.uuid4().hex[:8]}",
            title=title,
            description=description,
            assigned_to=assigned_to,
            priority=priority,
            status="todo",
            due_date=due_date,
            dependencies=dependencies or [],
        )

    def decompose_task(
        self,
        task_title: str,
        goal_description: str,
    ) -> TaskDecomposition:
        """Break down a high-level feature or objective into actionable subtasks with dependencies."""
        subtasks = [
            TaskItem(
                task_id=f"sub_{uuid.uuid4().hex[:6]}",
                title=f"1. Requirements & Design: {task_title}",
                description=f"Define specifications and interface contracts for {goal_description}",
                priority="high",
                status="todo",
                dependencies=[],
            ),
            TaskItem(
                task_id=f"sub_{uuid.uuid4().hex[:6]}",
                title=f"2. Core Implementation: {task_title}",
                description=f"Implement business logic, schemas, and adapters for {task_title}",
                priority="high",
                status="todo",
                dependencies=[],
            ),
            TaskItem(
                task_id=f"sub_{uuid.uuid4().hex[:6]}",
                title=f"3. Integration & Automated Tests: {task_title}",
                description=f"Validate end-to-end functionality, regressions, and security boundaries",
                priority="medium",
                status="todo",
                dependencies=[],
            ),
        ]

        # Chain dependencies
        subtasks[1].dependencies.append(subtasks[0].task_id)
        subtasks[2].dependencies.append(subtasks[1].task_id)

        order = [s.title for s in subtasks]
        return TaskDecomposition(
            parent_task_title=task_title,
            subtasks=subtasks,
            estimated_total_hours=16.0,
            recommended_execution_order=order,
        )

    def detect_blockers(self, tasks: List[TaskItem]) -> List[BlockerReport]:
        """Inspect task dependencies and identify blocked work items."""
        task_map = {t.task_id: t for t in tasks}
        blockers: List[BlockerReport] = []

        for t in tasks:
            for dep_id in t.dependencies:
                dep_task = task_map.get(dep_id)
                if dep_task and dep_task.status != "completed":
                    blockers.append(
                        BlockerReport(
                            task_id=t.task_id,
                            task_title=t.title,
                            blocked_by_task_id=dep_task.task_id,
                            blocked_by_title=dep_task.title,
                            blocker_reason=f"Dependent prerequisite '{dep_task.title}' is currently {dep_task.status}.",
                            urgency="high" if t.priority in ("high", "critical") else "medium",
                        )
                    )
        return blockers

    def summarize_project(self, project_id: str, tasks: List[TaskItem]) -> ProjectSummary:
        """Generate high-level project status and upcoming deadline metrics."""
        total = len(tasks)
        completed = sum(1 for t in tasks if t.status == "completed")
        blocked = sum(1 for t in tasks if t.status == "blocked")
        in_prog = sum(1 for t in tasks if t.status == "in_progress")

        pct = round((completed / total * 100), 1) if total > 0 else 0.0
        impending = [t for t in tasks if t.due_date and t.status != "completed"][:5]

        return ProjectSummary(
            project_id=project_id,
            total_tasks=total,
            completed_tasks=completed,
            blocked_tasks=blocked,
            in_progress_tasks=in_prog,
            completion_percentage=pct,
            impending_deadlines=impending,
        )

    def create_bulk_change_approval(
        self,
        context: TenantContext,
        action: str,
        task_count: int,
        details: str,
    ) -> ApprovalRequest:
        """Request explicit human authorization before executing bulk changes or deletions."""
        return approval_store.create_request(
            tenant_id=context.tenant_id,
            product_id="iryax.task_management",
            operation_name="delete_bulk_tasks" if "delete" in action.lower() else "bulk_task_modification",
            payload={
                "action": action,
                "task_count": task_count,
                "details": details,
                "requested_by": context.user_id,
            },
            required_roles=[Role.SUPER_ADMIN, Role.TENANT_ADMIN, Role.TASK_LEAD],
        )
