"""Multi-Agent Orchestrator — Central Dispatcher for Iryax AI Engine.

Connects the main chatbot backend to all 7 specialized product subagents:
1. Recruitment Agent
2. Attendance & Payroll Agent
3. Task Management Agent
4. Medical Camps Agent
5. OP Management Agent
6. Coworking Space Agent
7. Lab Management Agent

Intelligently classifies user queries:
- Dispatches operational/workflow tasks to the appropriate specialized subagent.
- Fallbacks to Groq RAG over ChromaDB for general product & company knowledge.
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
import re
import sys
from collections.abc import Iterator
from typing import Any, Dict, List, Optional, Tuple

# Ensure subagents/src is in sys.path
BACKEND_ROOT = pathlib.Path(__file__).parent.resolve()
SUBAGENTS_SRC = BACKEND_ROOT / "subagents" / "src"
if str(SUBAGENTS_SRC) not in sys.path:
    sys.path.insert(0, str(SUBAGENTS_SRC))

# Import specialized subagents from anycode package
from subagents.src.anycode.agents.products.base_agent import BaseProductAgent
from subagents.src.anycode.agents.products.coworking.agent import CoworkingAgent
from subagents.src.anycode.agents.products.lab_management.agent import LabManagementAgent
from subagents.src.anycode.agents.products.medical_camps.agent import MedicalCampsAgent
from subagents.src.anycode.agents.products.op_management.agent import OPManagementAgent
from subagents.src.anycode.agents.products.payroll.agent import PayrollAgent
from subagents.src.anycode.agents.products.recruitment.agent import RecruitmentAgent
from subagents.src.anycode.agents.products.shared_schemas import (
    AgentRequest,
    AgentResponse,
    ApprovalRequest,
    ApprovalStatus,
    ExecutionStatus,
    ProductId,
    Role,
    TenantContext,
)
from subagents.src.anycode.agents.products.shared_services import approval_service, audit_service
from subagents.src.anycode.agents.products.task_management.agent import TaskManagementAgent

from rag_pipeline import generate_rag_response

logger = logging.getLogger(__name__)


# ── Subagent Intent Matching Rules ──────────────────────────────────────────

INTENT_RULES: Dict[ProductId, Dict[str, Any]] = {
    ProductId.RECRUITMENT: {
        "keywords": [
            "resume", "cv", "candidate", "recruitment", "recruiter", "job posting", "job description",
            "hire", "hiring", "interview", "shortlist", "ats", "applicant", "job offer", "qualification",
            "pipeline", "ingrainhire"
        ],
        "default_intent": "match_candidate",
    },
    ProductId.PAYROLL: {
        "keywords": [
            "payroll", "salary", "attendance", "overtime", "payslip", "disbursement",
            "shift", "anomalies", "compensation", "payout", "timesheet", "employee", "staff",
            "roster", "timelyhealth", "deduction"
        ],
        "default_intent": "reconcile_attendance",
    },
    ProductId.TASK_MANAGEMENT: {
        "keywords": [
            "task", "project", "backlog", "sprint", "blocker", "epic", "decompose",
            "bottleneck", "subtask", "milestone", "kanban", "board", "velocity", "workload"
        ],
        "default_intent": "decompose_task",
    },
    ProductId.MEDICAL_CAMPS: {
        "keywords": [
            "medical camp", "camp", "vitals", "triage", "blood pressure", "glucose",
            "patient intake", "clinical triage", "camp registration", "volunteer", "screening",
            "health camp"
        ],
        "default_intent": "validate_vitals",
    },
    ProductId.OP_MANAGEMENT: {
        "keywords": [
            "doctor", "outpatient", "op clinic", "clinic", "token", "consultation",
            "appointment", "doctor availability", "op queue", "op management", "schedule", "reception"
        ],
        "default_intent": "check_doctor_availability",
    },
    ProductId.COWORKING: {
        "keywords": [
            "coworking", "desk", "cabin", "meeting room", "book seat", "seat availability",
            "desk availability", "coworking space", "refund for booking", "flexi desk", "hot desk",
            "workspace", "occupancy"
        ],
        "default_intent": "check_seat_availability",
    },
    ProductId.LAB_MANAGEMENT: {
        "keywords": [
            "lab", "test order", "diagnostic", "blood test", "specimen", "pathology",
            "lab report", "sample registration", "lab result", "abnormal result", "accessioning",
            "pathologist"
        ],
        "default_intent": "create_lab_order",
    },
}


class AgentOrchestrator:
    """Coordinates and routes requests across the 7 Iryax product subagents."""

    _AGENT_FACTORIES = {
        ProductId.RECRUITMENT: RecruitmentAgent,
        ProductId.PAYROLL: PayrollAgent,
        ProductId.TASK_MANAGEMENT: TaskManagementAgent,
        ProductId.MEDICAL_CAMPS: MedicalCampsAgent,
        ProductId.OP_MANAGEMENT: OPManagementAgent,
        ProductId.COWORKING: CoworkingAgent,
        ProductId.LAB_MANAGEMENT: LabManagementAgent,
    }

    def __init__(self):
        self._agents: Dict[ProductId, BaseProductAgent] = {
            pid: factory() for pid, factory in self._AGENT_FACTORIES.items()
        }
        logger.info("Initialized AgentOrchestrator with %d subagents.", len(self._agents))

    def restart_agent(self, product_id: ProductId | str) -> BaseProductAgent:
        """Self-healing recovery: re-instantiates a failed or degraded subagent."""
        target_pid = None
        if isinstance(product_id, str):
            clean_id = product_id.lower().replace("iryax.", "").strip()
            for pid in self._AGENT_FACTORIES:
                if (
                    clean_id == pid.value.lower().replace("iryax.", "").strip()
                    or clean_id == pid.value.lower()
                    or clean_id == pid.name.lower()
                ):
                    target_pid = pid
                    break
        else:
            target_pid = product_id

        if not target_pid or target_pid not in self._AGENT_FACTORIES:
            raise ValueError(f"Unknown agent for restart: {product_id}")

        factory = self._AGENT_FACTORIES[target_pid]
        new_instance = factory()
        self._agents[target_pid] = new_instance
        logger.info("Restarted and reloaded subagent %s successfully.", target_pid.value)
        return new_instance

    def get_agent(self, product_id: ProductId | str) -> Optional[BaseProductAgent]:
        """Retrieve a specific subagent by product ID, short name, or key string."""
        if isinstance(product_id, str):
            clean_id = product_id.lower().replace("iryax.", "").strip()
            for pid, ag in self._agents.items():
                pid_clean = pid.value.lower().replace("iryax.", "").strip()
                if (
                    clean_id == pid_clean
                    or clean_id == pid.value.lower()
                    or clean_id == pid.name.lower()
                    or clean_id in ag.name.lower()
                ):
                    return ag
            return None
        return self._agents.get(product_id)

    def list_subagents(self) -> List[Dict[str, Any]]:
        """List metadata and status for all connected product subagents."""
        summary = []
        for pid, agent in self._agents.items():
            summary.append({
                "product_id": pid.value,
                "name": agent.name,
                "description": agent.description,
                "supported_intents": agent.supported_intents,
                "tools": agent.list_tools(),
                "status": "online",
            })
        return summary

    def classify_query(self, query: str) -> Optional[ProductId]:
        """Determines if a query targets a specific subagent based on pattern rules."""
        q_lower = query.lower()
        scored_matches: List[Tuple[int, ProductId]] = []

        for pid, rule in INTENT_RULES.items():
            matches = 0
            for kw in rule["keywords"]:
                # Matches exact keyword or plural/verb forms (e.g. candidate/candidates, hire/hiring)
                pattern = r"\b" + re.escape(kw) + r"(?:s|es|ed|ing)?\b"
                if re.search(pattern, q_lower):
                    matches += 1
            if matches > 0:
                scored_matches.append((matches, pid))

        if scored_matches:
            # Sort by number of keyword matches descending
            scored_matches.sort(key=lambda x: x[0], reverse=True)
            return scored_matches[0][1]

        return None

    def execute_subagent(
        self,
        product_id: ProductId | str,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
        role: Role = Role.TENANT_ADMIN,
        user_id: str = "user_orchestrator",
        tenant_id: str = "tenant_iryax_global",
    ) -> AgentResponse:
        """Directly invoke a subagent workflow with role and tenant context."""
        agent = self.get_agent(product_id)
        if not agent:
            raise ValueError(f"Unknown product subagent: {product_id}")

        context = TenantContext(
            tenant_id=tenant_id,
            user_id=user_id,
            roles=[role],
        )

        request = AgentRequest(
            query=query,
            context=context,
            parameters=parameters or {},
        )

        audit_service.record(
            tenant_id=tenant_id,
            user_id=user_id,
            product_id=agent.product_id,
            action=f"execute:{query[:30]}",
            status="initiated",
        )

        # Execute through BaseProductAgent.execute() to enforce RBAC, audit, and idempotency
        response = agent.execute(request)

        audit_service.record(
            tenant_id=tenant_id,
            user_id=user_id,
            product_id=agent.product_id,
            action=f"execute:{query[:30]}",
            status=response.status.value,
        )

        return response

    def dispatch_streaming(
        self,
        query: str,
        history: Optional[List[Dict[str, str]]] = None,
        role: Role = Role.TENANT_ADMIN,
        user_id: str = "user_orchestrator",
        tenant_id: str = "tenant_iryax_global",
    ) -> Iterator[str]:
        """Routes query to either a specialized subagent or fallback to Groq RAG."""
        matched_product = self.classify_query(query)

        if matched_product is not None:
            # Dispatch to specialized product subagent
            agent = self._agents[matched_product]
            logger.info("Routing query to specialized subagent: %s", agent.name)

            try:
                response = self.execute_subagent(
                    product_id=matched_product,
                    query=query,
                    parameters={},
                    role=role,
                    user_id=user_id,
                    tenant_id=tenant_id,
                )

                # Stream initial dispatch acknowledgement
                badge_token = f"🤖 **{agent.name}**\n\n"
                yield json.dumps({"token": badge_token, "sources": [f"agent:{matched_product.value}"]}) + "\n"

                # Stream response body
                body_token = response.response_text + "\n\n"
                yield json.dumps({"token": body_token, "sources": [f"agent:{matched_product.value}"]}) + "\n"

                # If subagent triggered a Human-In-The-Loop approval gate, append notification
                if response.approval_request:
                    appr_token = (
                        f"> ⚠️ **Action Gated**: Operation `{response.approval_request.operation_name}` "
                        f"requires approval (`{response.approval_request.approval_id}`). "
                        f"Review in the Approvals Center before execution."
                    )
                    yield json.dumps({"token": appr_token, "sources": [f"agent:{matched_product.value}"]}) + "\n"

                # If tools were executed, list them in metadata
                tools_used = [t.tool_name for t in response.tools_executed]
                sources = [f"agent:{matched_product.value}"]
                if tools_used:
                    sources.extend([f"tool:{t}" for t in tools_used])

                # Terminal NDJSON line
                yield json.dumps({
                    "token": "",
                    "sources": sources,
                    "answer": response.response_text,
                    "status": response.status.value,
                    "agent": agent.name,
                }) + "\n"
                return

            except Exception as e:
                logger.error("Subagent execution error (%s): %s", agent.name, e)
                err_text = f"Subagent `{agent.name}` encountered an error: {e}"
                yield json.dumps({"token": err_text, "sources": [f"agent:{matched_product.value}"]}) + "\n"
                return

        # Fallback: General inquiry routed to Groq RAG pipeline over ChromaDB
        for chunk in generate_rag_response(query, history or []):
            yield chunk

    def list_approvals(self, tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all pending Human-In-The-Loop approval requests across subagents."""
        all_apprs = approval_service.list_all(tenant_id=tenant_id)
        return [
            {
                "approval_id": a.approval_id,
                "tenant_id": a.tenant_id,
                "product_id": a.product_id.value,
                "operation_name": a.operation_name,
                "payload": a.payload,
                "required_roles": [r.value for r in a.required_roles],
                "status": a.status.value,
                "decided_by": a.decided_by,
                "decided_at": a.decided_at,
                "rejection_reason": a.rejection_reason,
            }
            for a in all_apprs
        ]

    def decide_approval(
        self,
        approval_id: str,
        approve: bool,
        reviewer_id: str = "admin_reviewer",
        role: Role = Role.TENANT_ADMIN,
        tenant_id: str = "tenant_iryax_global",
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Approve or reject a pending subagent operation."""
        context = TenantContext(
            tenant_id=tenant_id,
            user_id=reviewer_id,
            roles=[role],
        )
        resolved = approval_service.decide(
            approval_id=approval_id,
            context=context,
            approve=approve,
            reason=reason,
        )
        return {
            "approval_id": resolved.approval_id,
            "status": resolved.status.value,
            "decided_by": resolved.decided_by,
            "decided_at": resolved.decided_at,
            "rejection_reason": resolved.rejection_reason,
        }


# Global singleton orchestrator
orchestrator = AgentOrchestrator()
