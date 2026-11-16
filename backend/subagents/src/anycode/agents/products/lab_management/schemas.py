"""Lab Management domain schemas."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class LabTest(BaseModel):
    test_id: str
    test_name: str
    category: str               # "haematology" | "biochemistry" | "microbiology" | "radiology"
    sample_type: str            # "blood" | "urine" | "swab" | "tissue"
    turnaround_hours: int
    price: float
    requires_fasting: bool = False


class Sample(BaseModel):
    sample_id: str
    patient_id: str
    test_ids: List[str]
    collected_at: str
    collected_by: str
    status: str = "collected"   # collected | processing | analysed | reported


class LabResult(BaseModel):
    result_id: str
    sample_id: str
    patient_id: str
    test_id: str
    values: Dict[str, Any]      # raw analyte key-value pairs
    reference_range: Dict[str, Any] = Field(default_factory=dict)
    interpretation: Optional[str] = None
    flag_abnormal: bool = False
    verified_by: Optional[str] = None   # pathologist ID
    released: bool = False              # true only after pathologist approval


class LabOrder(BaseModel):
    order_id: str
    patient_id: str
    ordered_by: str             # doctor ID
    test_ids: List[str]
    priority: str = "routine"   # "routine" | "urgent" | "stat"
    status: str = "ordered"
    tenant_id: str


class LabReportSummary(BaseModel):
    order_id: str
    patient_id: str
    tests_completed: int
    tests_pending: int
    abnormal_flags: int
    report_ready: bool
