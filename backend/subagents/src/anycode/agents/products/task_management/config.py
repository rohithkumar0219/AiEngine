"""Task management product configuration."""

from __future__ import annotations

import os
from pydantic import BaseModel


class TaskManagementConfig(BaseModel):
    api_url: str = os.getenv("TASKMANAGEMENT_API_URL", "")
    api_key: str = os.getenv("TASKMANAGEMENT_API_KEY", "")
    default_subtask_effort_hours: float = 4.0
    bulk_action_threshold: int = 5

    @property
    def is_backend_connected(self) -> bool:
        return bool(self.api_url and self.api_key)


task_config = TaskManagementConfig()
