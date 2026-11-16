"""Recruitment product configuration."""

from __future__ import annotations

import os
from pydantic import BaseModel


class RecruitmentConfig(BaseModel):
    api_url: str = os.getenv("INGRAINHIRE_API_URL", "")
    api_key: str = os.getenv("INGRAINHIRE_API_KEY", "")
    default_interview_duration_mins: int = 45
    min_match_score_for_interview: float = 60.0
    require_recruiter_offer_approval: bool = True

    @property
    def is_backend_connected(self) -> bool:
        return bool(self.api_url and self.api_key)


recruitment_config = RecruitmentConfig()
