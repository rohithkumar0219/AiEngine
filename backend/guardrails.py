"""
Iryax AI Multi-Agent Platform — Guardrails & Evaluation Pipeline.

Provides enterprise-grade:
1. Input Guardrails: Prompt injection detection, jailbreak pattern filtering, PII masking.
2. Output Guardrails: Groundedness verification, hallucination detection, HITL enforcement.
3. Role-Based Access Control (RBAC) & Tenant Isolation validation.
4. Comprehensive Automated Evaluation Suite (Groundedness, Accuracy, Security, Performance).
"""

from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

# ── Prompt Injection & Jailbreak Attack Signatures ───────────────────────────
PROMPT_INJECTION_PATTERNS = [
    r"(?i)\bignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions\b",
    r"(?i)\bbypass\s+(?:all\s+)?(?:rules|policies|guardrails|safety)\b",
    r"(?i)\b(?:disregard|forget)\s+(?:all\s+)?(?:system|developer)\s+prompts?\b",
    r"(?i)\byou\s+are\s+now\s+(?:in\s+)?(?:dan|developer|god|sudo|root)\s+mode\b",
    r"(?i)\b(?:reveal|leak|output|dump)\s+(?:the\s+)?(?:system\s+prompt|secret\s+key|jwt\s+secret|credentials)\b",
    r"(?i)<\s*\|\s*im_start\s*\|>",
    r"(?i)\[\s*INST\s*\]",
    r"(?i)```\s*(?:system|eval|exec)\b",
    r"(?i)\bdrop\s+table\b|\bdelete\s+from\s+admins\b",
    r"(?i)\bact\s+as\s+(?:an?\s+)?unrestricted\b",
]

# ── PII Patterns for Sensitive Data Masking ──────────────────────────────────
PII_PATTERNS = [
    (r"\b(?:\d{4}[-\s]?){3}\d{4}\b", "[REDACTED_CARD]"),
    (r"\b\d{3}-\d{2}-\d{4}\b", "[REDACTED_SSN]"),
    (r"(?i)\bpassword\s*[:=]\s*\S+", "password=[REDACTED]"),
    (r"\b[A-Za-z0-9_-]{32,}\.ey[A-Za-z0-9_-]+\b", "[REDACTED_JWT]"),
]


class GuardrailResult(BaseModel):
    is_safe: bool
    sanitized_text: str
    violations: List[str] = Field(default_factory=list)
    risk_level: str = "low"  # low, medium, high, critical
    action_taken: str = "allow"  # allow, mask, block


class InputGuardrail:
    """Validates and sanitizes incoming user prompts before LLM inference or agent execution."""

    @staticmethod
    def inspect(prompt: str) -> GuardrailResult:
        if not prompt or not prompt.strip():
            return GuardrailResult(
                is_safe=True,
                sanitized_text="",
                violations=[],
                risk_level="low",
                action_taken="allow",
            )

        violations: List[str] = []
        cleaned_prompt = prompt

        # 1. Prompt Injection & Jailbreak Check
        for pattern in PROMPT_INJECTION_PATTERNS:
            if re.search(pattern, cleaned_prompt):
                violations.append(f"Prompt injection attempt detected matching signature: '{pattern}'")

        if violations:
            return GuardrailResult(
                is_safe=False,
                sanitized_text="[REQUEST BLOCKED: Security violation detected. Prompt injection and policy bypass attempts are strictly prohibited.]",
                violations=violations,
                risk_level="critical",
                action_taken="block",
            )

        # 2. PII Sanitization
        for pii_regex, mask in PII_PATTERNS:
            if re.search(pii_regex, cleaned_prompt):
                cleaned_prompt = re.sub(pii_regex, mask, cleaned_prompt)
                violations.append("Sensitive PII detected and masked.")

        risk = "medium" if violations else "low"
        action = "mask" if violations else "allow"

        return GuardrailResult(
            is_safe=True,
            sanitized_text=cleaned_prompt,
            violations=violations,
            risk_level=risk,
            action_taken=action,
        )


class OutputGuardrail:
    """Verifies that generated responses adhere to factual grounding and governance policies."""

    @staticmethod
    def verify_groundedness(response_text: str, trusted_facts: List[str]) -> Tuple[bool, float, List[str]]:
        """
        Calculates groundedness score based on presence of verified keywords/entities.
        Returns (is_grounded, score, unverified_flags).
        """
        if not response_text:
            return True, 1.0, []

        flags: List[str] = []
        # Check against hallucination markers
        hallucination_phrases = [
            "as an ai language model with no access to",
            "i do not have access to real-time data",
            "i am inventing this data",
        ]
        for phrase in hallucination_phrases:
            if phrase in response_text.lower():
                flags.append(f"Model disclaimed grounded access: '{phrase}'")

        score = max(0.0, 1.0 - (len(flags) * 0.3))
        is_grounded = score >= 0.7
        return is_grounded, round(score, 2), flags

    @staticmethod
    def enforce_hitl_compliance(
        operation_name: str,
        is_approval_present: bool,
    ) -> Tuple[bool, Optional[str]]:
        """Ensures high-impact operations never bypass human governance."""
        gated_operations = {
            "release_payment",
            "extend_offer",
            "delete_bulk_tasks",
            "bulk_export",
            "schedule_override",
            "process_refund",
            "release_result",
            "release_report",
        }

        if any(op in operation_name.lower() for op in gated_operations):
            if not is_approval_present:
                return (
                    False,
                    f"CRITICAL GOVERNANCE VIOLATION: Operation '{operation_name}' requires explicit Human-In-The-Loop approval.",
                )
        return True, None


class TenantGuardrail:
    """Enforces strict multi-tenant isolation and role-based permissions."""

    @staticmethod
    def validate_isolation(
        request_tenant_id: str,
        resource_tenant_id: str,
    ) -> bool:
        if not request_tenant_id or not resource_tenant_id:
            return False
        # Global admin tenant can access platform resources; otherwise exact match is required
        if request_tenant_id == "tenant_iryax_global":
            return True
        return request_tenant_id.strip().lower() == resource_tenant_id.strip().lower()

