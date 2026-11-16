"""Payroll product configuration."""

from __future__ import annotations

import os
from pydantic import BaseModel


class PayrollConfig(BaseModel):
    api_url: str = os.getenv("TIMELYHEALTH_API_URL", "")
    api_key: str = os.getenv("TIMELYHEALTH_API_KEY", "")
    standard_monthly_days: int = 22
    overtime_multiplier: float = 1.5
    statutory_deduction_rate: float = 0.12
    max_safe_daily_hours: float = 14.0

    @property
    def is_backend_connected(self) -> bool:
        return bool(self.api_url and self.api_key)


payroll_config = PayrollConfig()
