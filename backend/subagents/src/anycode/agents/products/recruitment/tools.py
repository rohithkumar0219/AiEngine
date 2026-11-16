"""Recruitment tool implementations."""

from __future__ import annotations

import uuid
from typing import List
from anycode.agents.products.recruitment.schemas import (
    CandidateProfile,
    CommunicationDraft,
    InterviewSlot,
    JobPosting,
    MatchScore,
)
from anycode.agents.products.recruitment.services import recruitment_service


def parse_resume_tool(resume_text: str) -> CandidateProfile:
    return recruitment_service.parse_resume(resume_text)


def match_candidate_tool(candidate: CandidateProfile, job: JobPosting) -> MatchScore:
    return recruitment_service.match_candidate(candidate, job)


def schedule_interview_tool(
    candidate_name: str,
    job_id: str,
    scheduled_time: str,
    interviewer: str = "Lead Recruiter",
) -> InterviewSlot:
    return InterviewSlot(
        interview_id=f"int_{uuid.uuid4().hex[:8]}",
        candidate_id=f"cand_{uuid.uuid4().hex[:6]}",
        candidate_name=candidate_name,
        job_id=job_id,
        interviewer_name=interviewer,
        scheduled_time=scheduled_time,
        status="proposed_pending_confirmation",
    )


def draft_candidate_email_tool(
    candidate_email: str,
    candidate_name: str,
    job_title: str,
    next_step: str,
) -> CommunicationDraft:
    return CommunicationDraft(
        candidate_email=candidate_email,
        subject=f"Update regarding your application for {job_title} - Iryax",
        body=(
            f"Dear {candidate_name},\n\n"
            f"Thank you for interviewing with Iryax for {job_title}. "
            f"We would like to coordinate {next_step}. Please let us know your availability.\n\n"
            f"Best regards,\nIryax Recruitment Team"
        ),
        requires_recruiter_approval=True,
    )
