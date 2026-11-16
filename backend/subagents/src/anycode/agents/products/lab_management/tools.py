"""Lab Management domain tools."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List

from anycode.agents.products.lab_management.config import REQUIRE_PATHOLOGIST_RELEASE
from anycode.agents.products.lab_management.schemas import (
    LabOrder,
    LabReportSummary,
    LabResult,
    Sample,
)


def create_lab_order_tool(
    patient_id: str,
    ordered_by: str,
    test_ids: List[str],
    priority: str,
    tenant_id: str,
) -> LabOrder:
    """Create a new laboratory test order."""
    return LabOrder(
        order_id=f"LAB-{secrets.token_hex(4).upper()}",
        patient_id=patient_id,
        ordered_by=ordered_by,
        test_ids=test_ids,
        priority=priority,
        status="ordered",
        tenant_id=tenant_id,
    )


def register_sample_tool(
    patient_id: str,
    test_ids: List[str],
    collected_by: str,
) -> Sample:
    """Register a biological sample for processing."""
    return Sample(
        sample_id=f"SMP-{secrets.token_hex(4).upper()}",
        patient_id=patient_id,
        test_ids=test_ids,
        collected_at=datetime.now(timezone.utc).isoformat(),
        collected_by=collected_by,
        status="collected",
    )


def enter_results_tool(
    sample_id: str,
    patient_id: str,
    test_id: str,
    values: Dict[str, Any],
    reference_range: Dict[str, Any],
    interpretation: str | None = None,
) -> LabResult:
    """Record test result values and auto-flag abnormal findings."""
    flag = False
    for key, val in values.items():
        ref = reference_range.get(key, {})
        low = ref.get("low") if isinstance(ref, dict) else None
        high = ref.get("high") if isinstance(ref, dict) else None
        if isinstance(val, (int, float)):
            if (low is not None and val < low) or (high is not None and val > high):
                flag = True
                break

    return LabResult(
        result_id=f"RES-{secrets.token_hex(4).upper()}",
        sample_id=sample_id,
        patient_id=patient_id,
        test_id=test_id,
        values=values,
        reference_range=reference_range,
        interpretation=interpretation,
        flag_abnormal=flag,
        released=False,
    )


def release_result_tool(result: LabResult, verified_by: str) -> LabResult:
    """Mark a result as released after pathologist verification."""
    if REQUIRE_PATHOLOGIST_RELEASE and not verified_by:
        raise ValueError("Pathologist ID required to release results.")
    result.verified_by = verified_by
    result.released = True
    return result


def generate_lab_report_summary_tool(
    order_id: str,
    patient_id: str,
    results: List[LabResult],
    total_tests: int,
) -> LabReportSummary:
    """Summarise the completion state of a lab order."""
    completed = sum(1 for r in results if r.released)
    pending = total_tests - completed
    abnormal = sum(1 for r in results if r.flag_abnormal)
    return LabReportSummary(
        order_id=order_id,
        patient_id=patient_id,
        tests_completed=completed,
        tests_pending=pending,
        abnormal_flags=abnormal,
        report_ready=(pending == 0),
    )
