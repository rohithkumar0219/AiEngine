"""Task management service layer."""

from __future__ import annotations

import uuid
from typing import Dict, List, Optional
from anycode.agents.products.task_management.config import task_config
from anycode.agents.products.task_management.schemas import (
    BlockerReport,
    ProjectSummary,
    TaskDecomposition,
    TaskItem,
)


class TaskManagementService:
    """Service handling task decomposition, blocker detection, and project reporting."""

    def __init__(self):
        self._tasks: Dict[str, TaskItem] = {}

    @property
    def is_backend_connected(self) -> bool:
        return task_config.is_backend_connected

    def create(
        self,
        title: str,
        description: str,
        assigned_to: Optional[str] = None,
        priority: str = "medium",
        due_date: Optional[str] = None,
        dependencies: Optional[List[str]] = None,
    ) -> TaskItem:
        task = TaskItem(
            task_id=f"tsk_{uuid.uuid4().hex[:8]}",
            title=title,
            description=description,
            assigned_to=assigned_to,
            priority=priority,
            status="todo",
            due_date=due_date,
            dependencies=dependencies or [],
        )
        self._tasks[task.task_id] = task
        return task

    def decompose(self, title: str, goal: str) -> TaskDecomposition:
        s1 = TaskItem(task_id=f"sub_{uuid.uuid4().hex[:6]}", title=f"1. Spec & Contracts: {title}", description=goal, priority="high", status="todo")
        s2 = TaskItem(task_id=f"sub_{uuid.uuid4().hex[:6]}", title=f"2. Core Implementation: {title}", description=goal, priority="high", status="todo", dependencies=[s1.task_id])
        s3 = TaskItem(task_id=f"sub_{uuid.uuid4().hex[:6]}", title=f"3. Verification Tests: {title}", description=goal, priority="medium", status="todo", dependencies=[s2.task_id])

        subtasks = [s1, s2, s3]
        return TaskDecomposition(
            parent_task_title=title,
            subtasks=subtasks,
            estimated_total_hours=12.0,
            recommended_execution_order=[s.title for s in subtasks],
        )

    def detect_blockers(self, tasks: List[TaskItem]) -> List[BlockerReport]:
        t_map = {t.task_id: t for t in tasks}
        blockers: List[BlockerReport] = []
        for t in tasks:
            for dep_id in t.dependencies:
                dep = t_map.get(dep_id)
                if dep and dep.status != "completed":
                    blockers.append(
                        BlockerReport(
                            task_id=t.task_id,
                            task_title=t.title,
                            blocked_by_task_id=dep.task_id,
                            blocked_by_title=dep.title,
                            blocker_reason=f"Prerequisite '{dep.title}' is currently {dep.status}.",
                            urgency="high" if t.priority in ("high", "critical") else "medium",
                        )
                    )
        return blockers

    def summarize(self, project_id: str, tasks: List[TaskItem]) -> ProjectSummary:
        tot = len(tasks)
        done = sum(1 for t in tasks if t.status == "completed")
        blocked = sum(1 for t in tasks if t.status == "blocked")
        in_prog = sum(1 for t in tasks if t.status == "in_progress")
        pct = round((done / tot * 100), 1) if tot > 0 else 0.0
        impending = [t for t in tasks if t.due_date and t.status != "completed"][:5]

        return ProjectSummary(
            project_id=project_id,
            total_tasks=tot,
            completed_tasks=done,
            blocked_tasks=blocked,
            in_progress_tasks=in_prog,
            completion_percentage=pct,
            impending_deadlines=impending,
        )


task_service = TaskManagementService()
