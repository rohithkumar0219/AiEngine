"""Task Management Product Agent."""

from __future__ import annotations

from typing import Any, Dict, List

from iryax_platform.core.context import ProductId, Role
from iryax_platform.core.contracts import (
    AgentRequest,
    AgentResponse,
    ExecutionStatus,
    ToolCallRecord,
)
from iryax_platform.products.base import BaseProductAgent
from iryax_platform.products.task_management.schemas import TaskItem
from iryax_platform.products.task_management.service import TaskManagementService


class TaskManagementAgent(BaseProductAgent):
    """Product Agent for Iryax Task Management (work breakdown, assignments, blockers, dependencies)."""

    product_id = ProductId.TASK_MANAGEMENT
    name = "Iryax Task Management Agent"
    description = (
        "Assists with task creation, breakdown decomposition, assignment proposals, "
        "dependency tracking, blocker detection, and project status reporting."
    )
    supported_intents = [
        "create_task",
        "decompose_task",
        "detect_blockers",
        "summarize_project",
        "bulk_modify_tasks",
        "general_task_query",
    ]
    required_roles = [Role.TASK_LEAD, Role.EMPLOYEE, Role.TENANT_ADMIN]

    def __init__(self, service: TaskManagementService | None = None):
        super().__init__()
        self.service = service or TaskManagementService()
        self._register_default_tools()

    def _register_default_tools(self):
        self.register_tool("create_task", self.service.create_task)
        self.register_tool("decompose_task", self.service.decompose_task)
        self.register_tool("detect_blockers", self.service.detect_blockers)
        self.register_tool("summarize_project", self.service.summarize_project)
        self.register_tool("create_bulk_change_approval", self.service.create_bulk_change_approval)

    def handle_request(self, request: AgentRequest) -> AgentResponse:
        query_lower = request.query.lower()
        tools_executed: List[ToolCallRecord] = []

        # 1. Guardrail: Bulk destructive change or bulk delete
        if any(w in query_lower for w in ("bulk delete", "delete all", "purge tasks", "mass update", "bulk complete")):
            count = int(request.parameters.get("task_count", 10))
            action = request.parameters.get("action", "bulk_delete")

            call_record = self.execute_tool(
                "create_bulk_change_approval",
                {
                    "context": request.context,
                    "action": action,
                    "task_count": count,
                    "details": f"User '{request.context.user_id}' requested {action} affecting {count} tasks.",
                },
                request.context,
            )
            tools_executed.append(call_record)
            approval_req = call_record.output

            return AgentResponse(
                product_id=self.product_id,
                status=ExecutionStatus.PENDING_APPROVAL,
                response_text=(
                    f"Destructive or bulk task modifications require explicit human authorization. "
                    f"An approval request (ID: {approval_req.approval_id}) has been created for {count} tasks. "
                    f"A Task Lead or Tenant Admin must confirm before this action is executed."
                ),
                structured_data={"approval_id": approval_req.approval_id, "status": "pending_approval"},
                tools_executed=tools_executed,
                approval_request=approval_req,
            )

        # 2. Decompose a high-level task
        if any(w in query_lower for w in ("decompose", "break down", "breakdown", "subtasks", "plan feature")):
            title = request.parameters.get("title", request.query)
            goal = request.parameters.get("goal", "Deliver feature on schedule")

            call_record = self.execute_tool(
                "decompose_task",
                {"task_title": title, "goal_description": goal},
                request.context,
            )
            tools_executed.append(call_record)
            decomp = call_record.output

            return AgentResponse(
                product_id=self.product_id,
                status=ExecutionStatus.SUCCESS,
                response_text=(
                    f"Decomposed '{decomp.parent_task_title}' into {len(decomp.subtasks)} sequential subtasks. "
                    f"Estimated effort: {decomp.estimated_total_hours} hours."
                ),
                structured_data=decomp.model_dump(),
                tools_executed=tools_executed,
            )

        # 3. Create a single task
        if any(w in query_lower for w in ("create task", "add task", "new task", "assign task")):
            title = request.parameters.get("title", "New Task")
            desc = request.parameters.get("description", request.query)
            assigned = request.parameters.get("assigned_to")
            prio = request.parameters.get("priority", "medium")
            due = request.parameters.get("due_date")

            call_record = self.execute_tool(
                "create_task",
                {
                    "title": title,
                    "description": desc,
                    "assigned_to": assigned,
                    "priority": prio,
                    "due_date": due,
                },
                request.context,
            )
            tools_executed.append(call_record)
            task: TaskItem = call_record.output

            return AgentResponse(
                product_id=self.product_id,
                status=ExecutionStatus.SUCCESS,
                response_text=(
                    f"Created task '{task.title}' (ID: {task.task_id}) assigned to "
                    f"{task.assigned_to or 'Unassigned'} with priority {task.priority}."
                ),
                structured_data=task.model_dump(),
                tools_executed=tools_executed,
            )

        # 4. Detect blockers
        if any(w in query_lower for w in ("blocker", "blocked", "dependency", "bottleneck")):
            # Build sample tasks if none provided in parameters
            tasks_data = request.parameters.get("tasks", [])
            tasks: List[TaskItem] = []
            if isinstance(tasks_data, list) and tasks_data:
                for td in tasks_data:
                    if isinstance(td, dict):
                        tasks.append(TaskItem(**td))
            else:
                t1 = TaskItem(task_id="t1", title="Backend API Setup", description="Setup API endpoints", status="in_progress")
                t2 = TaskItem(task_id="t2", title="Frontend Integration", description="Connect UI to API", status="blocked", dependencies=["t1"])
                tasks = [t1, t2]

            call_record = self.execute_tool("detect_blockers", {"tasks": tasks}, request.context)
            tools_executed.append(call_record)
            blockers = call_record.output

            return AgentResponse(
                product_id=self.product_id,
                status=ExecutionStatus.SUCCESS,
                response_text=(
                    f"Identified {len(blockers)} blocked tasks. "
                    + (" ".join([f"{b.task_title} is blocked by {b.blocked_by_title}." for b in blockers]) if blockers else "No active blockers found.")
                ),
                structured_data={"blockers": [b.model_dump() for b in blockers]},
                tools_executed=tools_executed,
            )

        # 5. Check live backend sync
        if "sync" in query_lower or "taskmanagement" in query_lower:
            if not self.service.is_backend_connected():
                return AgentResponse(
                    product_id=self.product_id,
                    status=ExecutionStatus.BLOCKED_BACKEND,
                    response_text=(
                        "Live Iryax Task Management backend is not configured in this environment "
                        "(missing TASKMANAGEMENT_API_URL). Local task breakdown and blocker analysis remain operational."
                    ),
                    backend_supported=False,
                    missing_backend_message="Missing TASKMANAGEMENT_API_URL",
                )

        # 6. Default
        return AgentResponse(
            product_id=self.product_id,
            status=ExecutionStatus.SUCCESS,
            response_text=(
                "Iryax Task Management Agent is active. You can create tasks, decompose complex goals "
                "into subtasks, trace dependency bottlenecks, or summarize project progress."
            ),
            tools_executed=[],
        )
