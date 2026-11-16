"""Lab Management Service and Backend Connector (Iryax Lab Management)."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from iryax_platform.core.audit import approval_store
from iryax_platform.core.context import Role, TenantContext
from iryax_platform.core.contracts import ApprovalRequest
from iryax_platform.products.lab_management.schemas import (
    LabOrderIntake,
    LabReportDraft,
    QualityControlAlert,
    SampleTracking,
)


class LabManagementService:
    """Operations for diagnostic lab orders, barcode sample routing, QC calibration, and validation."""

    def __init__(self):
        self.api_url = os.getenv("LAB_API_URL")
        self.api_key = os.getenv("LAB_API_KEY")

    def is_backend_connected(self) -> bool:
        return bool(self.api_url and self.api_key)

    def intake_lab_order(
        self,
        patient_id: str,
        patient_name: str,
        tests: List[str],
        collection_type: str = "in_lab",
        scheduled_time: str = "Today",
        ordering_doctor: Optional[str] = None,
    ) -> LabOrderIntake:
        """Register a new diagnostic lab requisition."""
        return LabOrderIntake(
            order_id=f"ord_{uuid.uuid4().hex[:8]}",
            patient_id=patient_id,
            patient_name=patient_name,
            tests_requested=tests,
            collection_type=collection_type,
            scheduled_time=scheduled_time,
            ordering_doctor=ordering_doctor,
            status="order_received",
        )

    def generate_sample_barcode(
        self,
        order_id: str,
        sample_type: str = "blood_edta",
    ) -> SampleTracking:
        """Generate barcode tracking token and assign test department routing."""
        # Routing logic
        dept_map = {
            "blood_edta": "Hematology (CBC, ESR)",
            "serum": "Biochemistry (LFT, KFT, Lipid)",
            "urine": "Clinical Pathology",
            "swab": "Microbiology (Culture & Sensitivity)",
        }
        dept = dept_map.get(sample_type.lower(), "General Pathology")
        barcode = f"BAR-{uuid.uuid4().hex[:8].upper()}"

        return SampleTracking(
            sample_barcode=barcode,
            order_id=order_id,
            sample_type=sample_type,
            collected_at=datetime.now(timezone.utc).isoformat(),
            routing_department=dept,
            status="sample_collected",
        )

    def check_qc_outlier(
        self,
        sample_barcode: str,
        test_name: str,
        value: float,
        ref_low: float,
        ref_high: float,
    ) -> QualityControlAlert:
        """Evaluate raw instrument measurement against QC calibration bounds."""
        is_critical = value < (ref_low * 0.7) or value > (ref_high * 1.4)
        retest = is_critical or value < ref_low or value > ref_high

        return QualityControlAlert(
            alert_id=f"qc_{uuid.uuid4().hex[:8]}",
            sample_barcode=sample_barcode,
            test_name=test_name,
            measured_value=value,
            reference_low=ref_low,
            reference_high=ref_high,
            is_critical_outlier=is_critical,
            requires_retest=retest,
            notes=(
                f"Critical instrument variance detected for {test_name}. "
                f"Value {value} outside critical delta limit ({ref_low}-{ref_high}). Immediate rerun advised."
                if is_critical else
                (f"Measurement outside normal reference range ({ref_low}-{ref_high})." if retest else "Within QC bounds.")
            ),
        )

    def create_result_release_approval(
        self,
        context: TenantContext,
        order_id: str,
        patient_name: str,
        test_results: List[dict],
    ) -> ApprovalRequest:
        """Guardrail: Diagnostic test results MUST be validated by a certified Pathologist prior to release."""
        return approval_store.create_request(
            tenant_id=context.tenant_id,
            product_id="iryax.lab_management",
            operation_name="release_lab_results",
            payload={
                "order_id": order_id,
                "patient_name": patient_name,
                "test_results": test_results,
                "requested_by": context.user_id,
            },
            required_roles=[Role.SUPER_ADMIN, Role.PATHOLOGIST],
        )
