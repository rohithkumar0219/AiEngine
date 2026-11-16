"""Task management tool implementations."""

from __future__ import annotations

from typing import List, Optional
from anycode.agents.products.task_management.schemas import (
    BlockerReport,
    ProjectSummary,
    TaskDecomposition,
    TaskItem,
)
from anycode.agents.products.task_management.services import task_service


def create_task_tool(
    title: str,
    description: str,
    assigned_to: Optional[str] = None,
    priority: str = "medium",
    due_date: Optional[str] = None,
    dependencies: Optional[List[str]] = None,
) -> TaskItem:
    return task_service.create(title, description, assigned_to, priority, due_date, dependencies)


def decompose_task_tool(title: str, goal: str) -> TaskDecomposition:
    return task_service.decompose(title, goal)


def detect_blockers_tool(tasks: List[TaskItem]) -> List[BlockerReport]:
    return task_service.detect_blockers(tasks)


def summarize_project_tool(project_id: str, tasks: List[TaskItem]) -> ProjectSummary:
    return task_service.summarize(project_id, tasks)
