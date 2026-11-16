"""Notification Adapter for Product Agent Alerts and Communications."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class NotificationChannel(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    IN_APP = "in_app"
    WEBHOOK = "webhook"


class NotificationMessage(BaseModel):
    notification_id: str
    tenant_id: str
    recipient: str
    channel: NotificationChannel
    subject: str
    body: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    sent_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    status: str = "dispatched"


class NotificationAdapter:
    """Dispatches notifications across supported channels with audit tracking."""

    def __init__(self):
        self._sent: List[NotificationMessage] = []

    def send(
        self,
        tenant_id: str,
        recipient: str,
        subject: str,
        body: str,
        channel: NotificationChannel = NotificationChannel.IN_APP,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> NotificationMessage:
        import uuid

        msg = NotificationMessage(
            notification_id=f"notif_{uuid.uuid4().hex[:10]}",
            tenant_id=tenant_id,
            recipient=recipient,
            channel=channel,
            subject=subject,
            body=body,
            metadata=metadata or {},
        )
        self._sent.append(msg)
        logger.info(
            "Notification %s [%s] sent to %s: %s",
            msg.notification_id,
            channel,
            recipient,
            subject,
        )
        return msg

    def get_sent(self, tenant_id: str) -> List[NotificationMessage]:
        return [m for m in self._sent if m.tenant_id == tenant_id]


notification_adapter = NotificationAdapter()
