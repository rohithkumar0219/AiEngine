"""Recruitment product agent package."""

from iryax_platform.products.recruitment.agent import RecruitmentAgent
from iryax_platform.products.recruitment.schemas import (
    CandidateProfile,
    CommunicationDraft,
    InterviewSlot,
    JobDescription,
    MatchScore,
)
from iryax_platform.products.recruitment.service import RecruitmentService

__all__ = [
    "RecruitmentAgent",
    "CandidateProfile",
    "CommunicationDraft",
    "InterviewSlot",
    "JobDescription",
    "MatchScore",
    "RecruitmentService",
]
