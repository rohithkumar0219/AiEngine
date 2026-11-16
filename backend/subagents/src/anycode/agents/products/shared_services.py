"""Shared platform services (Audit, Approvals, Idempotency, Notifications)."""

from __future__ import annotations

import logging
import sys
import time
import uuid
from threading import Lock
from typing import Any, Dict, List, Optional
from anycode.agents.products.shared_schemas import (
    ApprovalRequest,
    ApprovalStatus,
    ProductId,
    Role,
    TenantContext,
)

logger = logging.getLogger(__name__)


class AuditService:
    """Persistent database-backed and memory-cached audit logging service."""

    def __init__(self):
        if not hasattr(sys, "_iryax_audit_entries"):
            sys._iryax_audit_entries = []
            sys._iryax_audit_lock = Lock()
        self._entries: List[Dict[str, Any]] = sys._iryax_audit_entries
        self._lock = sys._iryax_audit_lock

    def record(
        self,
        tenant_id: str,
        user_id: str,
        product_id: ProductId,
        action: str,
        status: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> str:
        audit_id = f"aud_{uuid.uuid4().hex[:12]}"
        prod_val = product_id.value if isinstance(product_id, ProductId) else str(product_id)
        now_ts = time.time()
        entry = {
            "audit_id": audit_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "product_id": prod_val,
            "action": action,
            "status": status,
            "details": details or {},
            "timestamp": now_ts,
        }
        with self._lock:
            self._entries.append(entry)

        # Persist to database if available
        try:
            import json
            from database import db_session, AuditRecord
            db_record = AuditRecord(
                audit_id=audit_id,
                tenant_id=tenant_id,
                user_id=user_id if user_id and not user_id.startswith("system") else None,
                product_id=prod_val,
                action=action,
                status=status,
                details_json=json.dumps(details or {}),
                timestamp=now_ts,
            )
            db_session.add(db_record)
            db_session.commit()
        except Exception as e:
            logger.debug("Database audit record persist skipped/deferred: %s", e)
            try:
                from database import db_session
                db_session.rollback()
            except Exception:
                pass

        return audit_id

    def query(self, tenant_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        # Query from database first to include persisted records across restarts
        try:
            import json
            from database import db_session, AuditRecord
            records = (
                db_session.query(AuditRecord)
                .filter(AuditRecord.tenant_id == tenant_id)
                .order_by(AuditRecord.timestamp.desc())
                .limit(limit)
                .all()
            )
            if records:
                return [
                    {
                        "audit_id": r.audit_id,
                        "tenant_id": r.tenant_id,
                        "user_id": r.user_id,
                        "product_id": r.product_id,
                        "action": r.action,
                        "status": r.status,
                        "details": json.loads(r.details_json or "{}"),
                        "timestamp": r.timestamp,
                    }
                    for r in records
                ]
        except Exception as e:
            logger.debug("Database query fallback to in-memory: %s", e)

        with self._lock:
            return [e for e in reversed(self._entries) if e["tenant_id"] == tenant_id][:limit]


class ApprovalService:
    """Coordinates Human-in-the-loop approvals with database persistence."""

    def __init__(self):
        if not hasattr(sys, "_iryax_approvals"):
            sys._iryax_approvals = {}
            sys._iryax_approval_lock = Lock()
        self._approvals: Dict[str, ApprovalRequest] = sys._iryax_approvals
        self._lock = sys._iryax_approval_lock

    def request_approval(
        self,
        tenant_id: str,
        product_id: ProductId,
        operation_name: str,
        payload: Dict[str, Any],
        required_roles: List[Role],
    ) -> ApprovalRequest:
        req = ApprovalRequest(
            approval_id=f"appr_{uuid.uuid4().hex[:10]}",
            tenant_id=tenant_id,
            product_id=product_id,
            operation_name=operation_name,
            payload=payload,
            required_roles=required_roles,
            status=ApprovalStatus.PENDING,
        )
        with self._lock:
            self._approvals[req.approval_id] = req

        # Persist to database
        try:
            import json
            from database import db_session, ApprovalRecord
            prod_val = product_id.value if isinstance(product_id, ProductId) else str(product_id)
            roles_val = [r.value if hasattr(r, "value") else str(r) for r in required_roles]
            db_record = ApprovalRecord(
                approval_id=req.approval_id,
                tenant_id=tenant_id,
                product_id=prod_val,
                operation_name=operation_name,
                payload_json=json.dumps(payload),
                required_roles_json=json.dumps(roles_val),
                status=req.status.value,
            )
            db_session.add(db_record)
            db_session.commit()
        except Exception as e:
            logger.debug("Database approval persist deferred: %s", e)
            try:
                from database import db_session
                db_session.rollback()
            except Exception:
                pass

        return req

    def decide(
        self,
        approval_id: str,
        context: TenantContext,
        approve: bool,
        reason: Optional[str] = None,
    ) -> ApprovalRequest:
        with self._lock:
            req = self._approvals.get(approval_id)
            if not req:
                # Attempt hydration from DB
                try:
                    import json
                    from database import db_session, ApprovalRecord
                    db_r = db_session.query(ApprovalRecord).filter_by(approval_id=approval_id).first()
                    if db_r:
                        req = ApprovalRequest(
                            approval_id=db_r.approval_id,
                            tenant_id=db_r.tenant_id,
                            product_id=ProductId(db_r.product_id),
                            operation_name=db_r.operation_name,
                            payload=json.loads(db_r.payload_json or "{}"),
                            required_roles=[Role(r) for r in json.loads(db_r.required_roles_json or "[]")],
                            status=ApprovalStatus(db_r.status),
                        )
                        self._approvals[req.approval_id] = req
                except Exception:
                    pass

            if not req:
                raise ValueError(f"Approval request {approval_id} not found")
            if req.tenant_id != context.tenant_id:
                raise PermissionError("Tenant isolation mismatch")
            if not context.has_any_role(req.required_roles):
                raise PermissionError(f"User {context.user_id} lacks authority to approve this action.")
            if req.status != ApprovalStatus.PENDING:
                raise ValueError(f"Approval {approval_id} has already been resolved.")

            req.decided_by = context.user_id
            req.decided_at = str(time.time())
            req.status = ApprovalStatus.APPROVED if approve else ApprovalStatus.REJECTED
            req.rejection_reason = reason if not approve else None

        # Update in DB
        try:
            from datetime import datetime, timezone
            from database import db_session, ApprovalRecord
            db_r = db_session.query(ApprovalRecord).filter_by(approval_id=approval_id).first()
            if db_r:
                db_r.status = req.status.value
                db_r.reviewed_by = context.user_id if not context.user_id.startswith("system") else None
                db_r.reviewed_at = datetime.now(timezone.utc)
                db_r.decision_reason = reason
                db_session.commit()
        except Exception as e:
            logger.debug("Database approval update deferred: %s", e)
            try:
                from database import db_session
                db_session.rollback()
            except Exception:
                pass

        return req

    def get(self, approval_id: str, tenant_id: str) -> Optional[ApprovalRequest]:
        with self._lock:
            req = self._approvals.get(approval_id)
            if req and req.tenant_id == tenant_id:
                return req

        # DB fallback
        try:
            import json
            from database import db_session, ApprovalRecord
            db_r = db_session.query(ApprovalRecord).filter_by(approval_id=approval_id, tenant_id=tenant_id).first()
            if db_r:
                req = ApprovalRequest(
                    approval_id=db_r.approval_id,
                    tenant_id=db_r.tenant_id,
                    product_id=ProductId(db_r.product_id),
                    operation_name=db_r.operation_name,
                    payload=json.loads(db_r.payload_json or "{}"),
                    required_roles=[Role(r) for r in json.loads(db_r.required_roles_json or "[]")],
                    status=ApprovalStatus(db_r.status),
                )
                with self._lock:
                    self._approvals[req.approval_id] = req
                return req
        except Exception:
            pass

        return None

    def list_all(self, tenant_id: Optional[str] = None) -> List[ApprovalRequest]:
        # Sync from DB
        try:
            import json
            from database import db_session, ApprovalRecord
            query = db_session.query(ApprovalRecord)
            if tenant_id:
                query = query.filter_by(tenant_id=tenant_id)
            for db_r in query.all():
                if db_r.approval_id not in self._approvals:
                    self._approvals[db_r.approval_id] = ApprovalRequest(
                        approval_id=db_r.approval_id,
                        tenant_id=db_r.tenant_id,
                        product_id=ProductId(db_r.product_id),
                        operation_name=db_r.operation_name,
                        payload=json.loads(db_r.payload_json or "{}"),
                        required_roles=[Role(r) for r in json.loads(db_r.required_roles_json or "[]")],
                        status=ApprovalStatus(db_r.status),
                    )
        except Exception:
            pass

        with self._lock:
            if tenant_id:
                return [r for r in self._approvals.values() if r.tenant_id == tenant_id]
            return list(self._approvals.values())


class IdempotencyService:
    """Prevents duplicate execution on retried actions."""

    def __init__(self, ttl: int = 3600):
        self._ttl = ttl
        self._store: Dict[str, tuple[float, Any]] = {}
        self._lock = Lock()

    def get(self, tenant_id: str, key: str) -> Optional[Any]:
        comp = f"{tenant_id}:{key}"
        now = time.time()
        with self._lock:
            entry = self._store.get(comp)
            if entry and now <= entry[0]:
                return entry[1]
            return None

    def put(self, tenant_id: str, key: str, value: Any) -> None:
        comp = f"{tenant_id}:{key}"
        with self._lock:
            self._store[comp] = (time.time() + self._ttl, value)


class NotificationService:
    """Multi-channel notification dispatcher."""

    def __init__(self):
        self._sent: List[Dict[str, Any]] = []

    def dispatch(
        self,
        tenant_id: str,
        recipient: str,
        subject: str,
        body: str,
        channel: str = "in_app",
    ) -> Dict[str, Any]:
        msg = {
            "notification_id": f"notif_{uuid.uuid4().hex[:8]}",
            "tenant_id": tenant_id,
            "recipient": recipient,
            "subject": subject,
            "body": body,
            "channel": channel,
            "timestamp": time.time(),
        }
        self._sent.append(msg)
        return msg


# Global singletons
audit_service = AuditService()
approval_service = ApprovalService()
idempotency_service = IdempotencyService()
notification_service = NotificationService()

# Ensure canonical module registration so both import paths share the exact same module
_this_module = sys.modules.get(__name__)
if _this_module:
    sys.modules.setdefault("subagents.src.anycode.agents.products.shared_services", _this_module)
    sys.modules.setdefault("anycode.agents.products.shared_services", _this_module)
