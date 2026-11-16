"""Task management domain schemas."""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class TaskItem(BaseModel):
    task_id: str
    title: str
    description: str
    assigned_to: Optional[str] = None
    priority: str = "medium"
    status: str = "todo"
    due_date: Optional[str] = None
    dependencies: List[str] = Field(default_factory=list)


class TaskDecomposition(BaseModel):
    parent_task_title: str
    subtasks: List[TaskItem]
    estimated_total_hours: float
    recommended_execution_order: List[str]


class BlockerReport(BaseModel):
    task_id: str
    task_title: str
    blocked_by_task_id: str
    blocked_by_title: str
    blocker_reason: str
    urgency: str


class ProjectSummary(BaseModel):
    project_id: str
    total_tasks: int
    completed_tasks: int
    blocked_tasks: int
    in_progress_tasks: int
    completion_percentage: float
    impending_deadlines: List[TaskItem]
