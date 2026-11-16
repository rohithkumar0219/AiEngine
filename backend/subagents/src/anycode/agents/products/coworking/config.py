"""Coworking Space config."""

from __future__ import annotations

import os

COWORKING_API_URL: str = os.getenv("COWORKING_API_URL", "http://localhost:8006")
HOT_DESK_HOURLY_RATE: float = float(os.getenv("HOT_DESK_HOURLY_RATE", "50.0"))
DEDICATED_MONTHLY_RATE: float = float(os.getenv("DEDICATED_MONTHLY_RATE", "5000.0"))
PRIVATE_OFFICE_MONTHLY_RATE: float = float(os.getenv("PRIVATE_OFFICE_MONTHLY_RATE", "15000.0"))
CANCELLATION_WINDOW_HOURS: int = int(os.getenv("CANCELLATION_WINDOW_HOURS", "24"))
REFUND_THRESHOLD_INR: float = float(os.getenv("REFUND_THRESHOLD_INR", "1000.0"))
