"""Medical Camps config."""

from __future__ import annotations

import os

CAMP_API_URL: str = os.getenv("CAMP_API_URL", "http://localhost:8004")
MAX_PATIENTS_PER_CAMP: int = int(os.getenv("MAX_PATIENTS_PER_CAMP", "500"))
TRIAGE_CRITICAL_SPO2_THRESHOLD: int = int(os.getenv("TRIAGE_CRITICAL_SPO2_THRESHOLD", "92"))
TRIAGE_CRITICAL_BP_SYSTOLIC: int = int(os.getenv("TRIAGE_CRITICAL_BP_SYSTOLIC", "180"))
PRIVACY_TOKEN_PREFIX: str = os.getenv("PRIVACY_TOKEN_PREFIX", "CAMP")
