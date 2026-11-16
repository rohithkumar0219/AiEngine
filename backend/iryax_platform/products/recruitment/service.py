"""Recruitment Service and Backend Connector (IngrainHire / Iryax Recruitment)."""

from __future__ import annotations

import os
import re
import uuid
from typing import Any, Dict, List, Optional

from iryax_platform.core.audit import approval_store
from iryax_platform.core.context import Role, TenantContext
from iryax_platform.core.contracts import ApprovalRequest
from iryax_platform.products.recruitment.schemas import (
    CandidateProfile,
    CommunicationDraft,
    InterviewSlot,
    JobDescription,
    MatchScore,
)


class RecruitmentService:
    """Service layer connecting to IngrainHire or executing offline heuristics."""

    def __init__(self):
        self.api_url = os.getenv("INGRAINHIRE_API_URL")
        self.api_key = os.getenv("INGRAINHIRE_API_KEY")

    def is_backend_connected(self) -> bool:
        return bool(self.api_url and self.api_key)

    def parse_resume(self, resume_text: str) -> CandidateProfile:
        """Extract structured candidate information from resume text."""
        # Simple extraction heuristics (LLM or regex)
        email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", resume_text)
        email = email_match.group(0) if email_match else "unknown@applicant.com"

        # Look for candidate name
        lines = [line.strip() for line in resume_text.strip().split("\n") if line.strip()]
        name = lines[0] if lines else "Candidate"
        if len(name) > 40 or "@" in name:
            name = "Candidate Applicant"

        # Skills heuristics
        common_skills = [
            "python", "fastapi", "react", "typescript", "sql", "docker",
            "kubernetes", "aws", "git", "machine learning", "pytorch",
            "leadership", "agile", "project management", "node.js"
        ]
        text_lower = resume_text.lower()
        skills = [s for s in common_skills if s in text_lower]

        # Experience heuristic
        exp_match = re.search(r"(\d+)\+?\s*years?(?:\s+of)?\s+experience", text_lower)
        years_exp = float(exp_match.group(1)) if exp_match else 2.0

        return CandidateProfile(
            candidate_id=f"cand_{uuid.uuid4().hex[:8]}",
            name=name,
            email=email,
            years_experience=years_exp,
            skills=skills,
            raw_resume_text=resume_text[:500],
        )

    def match_candidate(
        self,
        candidate: CandidateProfile,
        job: JobDescription,
    ) -> MatchScore:
        """Score candidate against job criteria."""
        req_skills_set = {s.lower() for s in job.required_skills}
        cand_skills_set = {s.lower() for s in candidate.skills}

        matched = list(cand_skills_set.intersection(req_skills_set))
        missing = list(req_skills_set - cand_skills_set)

        skill_pct = len(matched) / len(req_skills_set) if req_skills_set else 1.0
        exp_pct = min(1.0, candidate.years_experience / job.min_years_experience) if job.min_years_experience > 0 else 1.0

        final_score = round((skill_pct * 0.7 + exp_pct * 0.3) * 100, 1)

        recommendation = "Strong Match — Recommend Interview" if final_score >= 80 else (
            "Potential Match — Review Experience" if final_score >= 50 else "Not a Fit for Role"
        )

        return MatchScore(
            candidate_id=candidate.candidate_id,
            candidate_name=candidate.name,
            score=final_score,
            matched_skills=matched,
            missing_skills=missing,
            recommendation=recommendation,
        )

    def propose_interview(
        self,
        candidate_name: str,
        job_id: str,
        scheduled_time: str,
        interviewer: str,
    ) -> InterviewSlot:
        """Propose an interview calendar slot."""
        return InterviewSlot(
            interview_id=f"int_{uuid.uuid4().hex[:8]}",
            candidate_id=f"cand_{uuid.uuid4().hex[:6]}",
            candidate_name=candidate_name,
            job_id=job_id,
            interviewer_name=interviewer,
            scheduled_time=scheduled_time,
            status="proposed_pending_confirmation",
        )

    def draft_communication(
        self,
        candidate_email: str,
        candidate_name: str,
        job_title: str,
        next_step: str,
    ) -> CommunicationDraft:
        """Draft a recruiter-approved communication."""
        body = (
            f"Dear {candidate_name},\n\n"
            f"Thank you for your interest in the {job_title} role at Iryax. "
            f"We are excited to proceed with {next_step}. Please let us know your availability.\n\n"
            f"Best regards,\nIryax Recruitment Team"
        )
        return CommunicationDraft(
            candidate_email=candidate_email,
            subject=f"Update regarding your application for {job_title} - Iryax",
            body=body,
            requires_recruiter_approval=True,
        )

    def create_hire_offer_approval(
        self,
        context: TenantContext,
        candidate_name: str,
        job_title: str,
        offered_salary: float,
    ) -> ApprovalRequest:
        """Queue a hiring offer for explicit recruiter/admin approval."""
        return approval_store.create_request(
            tenant_id=context.tenant_id,
            product_id="iryax.recruitment",
            operation_name="extend_employment_offer",
            payload={
                "candidate_name": candidate_name,
                "job_title": job_title,
                "offered_salary": offered_salary,
                "requested_by": context.user_id,
            },
            required_roles=[Role.SUPER_ADMIN, Role.TENANT_ADMIN, Role.HR_ADMIN],
        )
