"""OP Management config."""

from __future__ import annotations

import os

OP_API_URL: str = os.getenv("OP_API_URL", "http://localhost:8005")
DEFAULT_SLOT_DURATION_MINUTES: int = int(os.getenv("DEFAULT_SLOT_DURATION_MINUTES", "15"))
MAX_DAILY_APPOINTMENTS_PER_DOCTOR: int = int(os.getenv("MAX_DAILY_APPOINTMENTS_PER_DOCTOR", "30"))
TOKEN_COUNTER_PREFIX: str = os.getenv("TOKEN_COUNTER_PREFIX", "OPD")
WALK_IN_BUFFER_SLOTS: int = int(os.getenv("WALK_IN_BUFFER_SLOTS", "5"))
