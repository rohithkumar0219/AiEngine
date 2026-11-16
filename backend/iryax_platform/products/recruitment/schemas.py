"""Typed schemas for Recruitment Agent."""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class CandidateProfile(BaseModel):
    candidate_id: str
    name: str
    email: str
    years_experience: float
    skills: List[str]
    current_title: Optional[str] = None
    education: Optional[str] = None
    raw_resume_text: Optional[str] = None


class JobDescription(BaseModel):
    job_id: str
    title: str
    department: str
    required_skills: List[str]
    min_years_experience: float
    location: str
    description: str


class MatchScore(BaseModel):
    candidate_id: str
    candidate_name: str
    score: float = Field(..., ge=0.0, le=100.0)
    matched_skills: List[str]
    missing_skills: List[str]
    recommendation: str


class InterviewSlot(BaseModel):
    interview_id: str
    candidate_id: str
    candidate_name: str
    job_id: str
    interviewer_name: str
    scheduled_time: str
    duration_minutes: int = 45
    status: str = "proposed"


class CommunicationDraft(BaseModel):
    candidate_email: str
    subject: str
    body: str
    requires_recruiter_approval: bool = True
