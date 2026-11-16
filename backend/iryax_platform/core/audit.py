"""Audit Logging and Human-in-the-Loop Approval Store."""

from __future__ import annotations

import json
import logging
import pathlib
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from threading import Lock

from iryax_platform.core.context import Role, TenantContext
from iryax_platform.core.contracts import ApprovalRequest, ApprovalStatus, AuditEntry

logger = logging.getLogger(__name__)

AUDIT_DIR = pathlib.Path(__file__).parents[2] / "data" / "analytics"
AUDIT_LOG_FILE = AUDIT_DIR / "audit_log.json"


class AuditLogger:
    """Thread-safe persistent audit logger enforcing compliance and traceability."""

    def __init__(self, log_path: pathlib.Path = AUDIT_LOG_FILE):
        self._path = log_path
        self._lock = Lock()
        self._in_memory: List[AuditEntry] = []
        self._ensure_dir()

    def _ensure_dir(self):
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning("Could not create audit log directory: %s", e)

    def log(self, entry: AuditEntry) -> None:
        with self._lock:
            self._in_memory.append(entry)
            try:
                with open(self._path, "a", encoding="utf-8") as f:
                    f.write(entry.model_dump_json() + "\n")
            except Exception as e:
                logger.error("Failed to persist audit log entry: %s", e)

    def query(
        self,
        tenant_id: str,
        product_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[AuditEntry]:
        with self._lock:
            matches = [
                e
                for e in reversed(self._in_memory)
                if e.tenant_id == tenant_id
                and (product_id is None or e.product_id == product_id)
            ]
            return matches[:limit]


class ApprovalStore:
    """Stores and coordinates Human-In-The-Loop approval gates for sensitive actions."""

    def __init__(self):
        self._lock = Lock()
        self._approvals: Dict[str, ApprovalRequest] = {}

    def create_request(
        self,
        tenant_id: str,
        product_id: Any,
        operation_name: str,
        payload: Dict[str, Any],
        required_roles: List[Role],
    ) -> ApprovalRequest:
        req = ApprovalRequest(
            approval_id=f"appr_{uuid.uuid4().hex[:12]}",
            tenant_id=tenant_id,
            product_id=product_id,
            operation_name=operation_name,
            payload=payload,
            required_roles=required_roles,
            status=ApprovalStatus.PENDING,
        )
        with self._lock:
            self._approvals[req.approval_id] = req
        logger.info(
            "Created approval request %s for %s (%s)",
            req.approval_id,
            operation_name,
            product_id,
        )
        return req

    def get_request(self, approval_id: str, tenant_id: str) -> Optional[ApprovalRequest]:
        with self._lock:
            req = self._approvals.get(approval_id)
            if req and req.tenant_id == tenant_id:
                return req
            return None

    def decide(
        self,
        approval_id: str,
        context: TenantContext,
        approve: bool,
        rejection_reason: Optional[str] = None,
    ) -> ApprovalRequest:
        with self._lock:
            req = self._approvals.get(approval_id)
            if not req:
                raise ValueError(f"Approval request {approval_id} not found")
            if req.tenant_id != context.tenant_id:
                raise PermissionError("Access denied: Tenant isolation mismatch")

            # Check if user has one of the required roles or is SUPER_ADMIN
            if not context.has_any_role(req.required_roles):
                raise PermissionError(
                    f"User {context.user_id} lacks required role for approval. Needed: {req.required_roles}"
                )

            if req.status != ApprovalStatus.PENDING:
                raise ValueError(f"Approval request {approval_id} is already {req.status}")

            req.decided_by = context.user_id
            req.decided_at = datetime.now(timezone.utc).isoformat()
            if approve:
                req.status = ApprovalStatus.APPROVED
            else:
                req.status = ApprovalStatus.REJECTED
                req.rejection_reason = rejection_reason or "Rejected by reviewer"

            return req


# Global singletons
audit_logger = AuditLogger()
approval_store = ApprovalStore()
