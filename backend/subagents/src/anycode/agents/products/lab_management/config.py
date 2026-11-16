"""Lab Management config."""

from __future__ import annotations

import os

LAB_API_URL: str = os.getenv("LAB_API_URL", "http://localhost:8007")
DEFAULT_TURNAROUND_HOURS: int = int(os.getenv("DEFAULT_TURNAROUND_HOURS", "24"))
STAT_TURNAROUND_HOURS: int = int(os.getenv("STAT_TURNAROUND_HOURS", "2"))
ABNORMAL_ALERT_WEBHOOK: str = os.getenv("ABNORMAL_ALERT_WEBHOOK", "")
REQUIRE_PATHOLOGIST_RELEASE: bool = os.getenv("REQUIRE_PATHOLOGIST_RELEASE", "true").lower() == "true"
