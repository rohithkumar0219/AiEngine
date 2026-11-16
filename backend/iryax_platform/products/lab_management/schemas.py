"""Typed schemas for Lab Management Agent."""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class LabOrderIntake(BaseModel):
    order_id: str
    patient_id: str
    patient_name: str
    tests_requested: List[str]
    collection_type: str = "in_lab"  # in_lab, home_collection
    scheduled_time: str
    ordering_doctor: Optional[str] = None
    status: str = "order_received"


class SampleTracking(BaseModel):
    sample_barcode: str
    order_id: str
    sample_type: str  # blood_edta, serum, urine, swab
    collected_at: str
    routing_department: str  # Hematology, Biochemistry, Microbiology, Pathology
    status: str = "sample_collected"  # sample_collected, in_transit, analyzing, completed


class QualityControlAlert(BaseModel):
    alert_id: str
    sample_barcode: str
    test_name: str
    measured_value: float
    reference_low: float
    reference_high: float
    is_critical_outlier: bool
    requires_retest: bool
    notes: str


class LabReportDraft(BaseModel):
    report_id: str
    order_id: str
    patient_name: str
    test_results: List[dict]
    is_validated_by_pathologist: bool = False
    release_status: str = "pending_pathologist_validation"
