"""Recruitment product manifest."""

from __future__ import annotations

MANIFEST = {
    "product_id": "iryax.recruitment",
    "name": "Iryax Recruitment",
    "version": "1.0.0",
    "description": "AI-powered Applicant Tracking System, resume parser, candidate matcher, and interview scheduler.",
    "intents": [
        "parse_resume",
        "match_candidates",
        "schedule_interview",
        "draft_communication",
        "extend_offer",
        "recruitment_overview",
    ],
    "required_roles": ["recruiter", "hr_admin", "tenant_admin", "super_admin"],
    "backend_service_env": "INGRAINHIRE_API_URL",
}
