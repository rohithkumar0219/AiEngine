"""Task Management product package."""

from anycode.agents.products.task_management.agent import TaskManagementAgent
from anycode.agents.products.task_management.config import TaskManagementConfig, task_config
from anycode.agents.products.task_management.manifest import MANIFEST
from anycode.agents.products.task_management.schemas import (
    BlockerReport,
    ProjectSummary,
    TaskDecomposition,
    TaskItem,
)

__all__ = [
    "TaskManagementAgent",
    "TaskManagementConfig",
    "task_config",
    "MANIFEST",
    "TaskItem",
    "TaskDecomposition",
    "BlockerReport",
    "ProjectSummary",
]
