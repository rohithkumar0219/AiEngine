"""Recruitment service layer."""

from __future__ import annotations

import re
import uuid
from typing import Dict, List, Optional
from anycode.agents.products.recruitment.config import recruitment_config
from anycode.agents.products.recruitment.schemas import CandidateProfile, JobPosting, MatchScore


class RecruitmentService:
    """Service handling job requisitions, candidate evaluation, and matching."""

    def __init__(self):
        self._jobs: Dict[str, JobPosting] = {}
        self._candidates: Dict[str, CandidateProfile] = {}

    @property
    def is_backend_connected(self) -> bool:
        return recruitment_config.is_backend_connected

    def parse_resume(self, text: str) -> CandidateProfile:
        email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text)
        email = email_match.group(0) if email_match else "applicant@domain.com"
        lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
        name = lines[0] if lines and len(lines[0]) < 35 and "@" not in lines[0] else "Candidate Applicant"

        common_skills = ["python", "fastapi", "react", "typescript", "sql", "docker", "kubernetes", "aws", "git"]
        skills = [s for s in common_skills if s in text.lower()]

        exp_match = re.search(r"(\d+)\+?\s*years?", text.lower())
        exp = float(exp_match.group(1)) if exp_match else 2.0

        cand = CandidateProfile(
            candidate_id=f"cand_{uuid.uuid4().hex[:8]}",
            name=name,
            email=email,
            years_experience=exp,
            skills=skills,
            raw_resume_text=text[:300],
        )
        self._candidates[cand.candidate_id] = cand
        return cand

    def match_candidate(self, candidate: CandidateProfile, job: JobPosting) -> MatchScore:
        req_set = {s.lower() for s in job.required_skills}
        cand_set = {s.lower() for s in candidate.skills}

        matched = list(cand_set.intersection(req_set))
        missing = list(req_set - cand_set)

        skill_pct = len(matched) / len(req_set) if req_set else 1.0
        exp_pct = min(1.0, candidate.years_experience / job.min_years_experience) if job.min_years_experience > 0 else 1.0

        final_score = round((skill_pct * 0.7 + exp_pct * 0.3) * 100, 1)
        rec = "Strong Match — Recommend Interview" if final_score >= 80 else (
            "Potential Match — Review Experience" if final_score >= 50 else "Not a Fit for Role"
        )

        return MatchScore(
            candidate_id=candidate.candidate_id,
            candidate_name=candidate.name,
            job_id=job.job_id,
            score=final_score,
            matched_skills=matched,
            missing_skills=missing,
            experience_gap_years=max(0.0, job.min_years_experience - candidate.years_experience),
            recommendation=rec,
        )


recruitment_service = RecruitmentService()
