"""Idempotency Store for Multi-Product Agent Operations."""

from __future__ import annotations

import time
from threading import Lock
from typing import Any, Dict, Optional


class IdempotencyStore:
    """In-memory thread-safe idempotency registry with TTL expiration."""

    def __init__(self, default_ttl_seconds: int = 3600):
        self._ttl = default_ttl_seconds
        self._lock = Lock()
        self._store: Dict[str, tuple[float, Any]] = {}

    def _cleanup_expired(self, now: float) -> None:
        expired_keys = [k for k, (exp, _) in self._store.items() if now > exp]
        for k in expired_keys:
            del self._store[k]

    def get(self, tenant_id: str, idempotency_key: str) -> Optional[Any]:
        composite_key = f"{tenant_id}:{idempotency_key}"
        now = time.time()
        with self._lock:
            self._cleanup_expired(now)
            entry = self._store.get(composite_key)
            if entry:
                exp, result = entry
                if now <= exp:
                    return result
            return None

    def set(
        self,
        tenant_id: str,
        idempotency_key: str,
        result: Any,
        ttl_seconds: Optional[int] = None,
    ) -> None:
        composite_key = f"{tenant_id}:{idempotency_key}"
        ttl = ttl_seconds or self._ttl
        now = time.time()
        with self._lock:
            self._cleanup_expired(now)
            self._store[composite_key] = (now + ttl, result)


idempotency_store = IdempotencyStore()
