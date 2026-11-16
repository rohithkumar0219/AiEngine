"""Recruitment product package."""

from anycode.agents.products.recruitment.agent import RecruitmentAgent
from anycode.agents.products.recruitment.config import RecruitmentConfig, recruitment_config
from anycode.agents.products.recruitment.manifest import MANIFEST
from anycode.agents.products.recruitment.schemas import (
    CandidateProfile,
    CommunicationDraft,
    InterviewSlot,
    JobPosting,
    MatchScore,
)

__all__ = [
    "RecruitmentAgent",
    "RecruitmentConfig",
    "recruitment_config",
    "MANIFEST",
    "CandidateProfile",
    "JobPosting",
    "MatchScore",
    "InterviewSlot",
    "CommunicationDraft",
]
