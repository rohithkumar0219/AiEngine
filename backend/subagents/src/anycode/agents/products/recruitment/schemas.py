"""Recruitment domain data schemas."""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class CandidateProfile(BaseModel):
    candidate_id: str
    name: str
    email: str
    years_experience: float = 0.0
    skills: List[str] = Field(default_factory=list)
    current_title: Optional[str] = None
    education: Optional[str] = None
    raw_resume_text: Optional[str] = None


class JobPosting(BaseModel):
    job_id: str
    title: str
    department: str
    required_skills: List[str]
    min_years_experience: float = 2.0
    location: str = "Remote / Hybrid"
    description: str = ""
    status: str = "active"


class MatchScore(BaseModel):
    candidate_id: str
    candidate_name: str
    job_id: str
    score: float = Field(..., ge=0.0, le=100.0)
    matched_skills: List[str]
    missing_skills: List[str]
    experience_gap_years: float = 0.0
    recommendation: str


class InterviewSlot(BaseModel):
    interview_id: str
    candidate_id: str
    candidate_name: str
    job_id: str
    interviewer_name: str
    scheduled_time: str
    status: str = "proposed"


class CommunicationDraft(BaseModel):
    candidate_email: str
    subject: str
    body: str
    requires_recruiter_approval: bool = True
