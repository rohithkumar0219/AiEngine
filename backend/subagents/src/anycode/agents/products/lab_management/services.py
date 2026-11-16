"""Lab Management services — domain business logic."""

from __future__ import annotations

from typing import List

from anycode.agents.products.lab_management.schemas import LabResult, Sample


class SampleService:
    """Sample lifecycle management."""

    def mark_processing(self, sample: Sample) -> Sample:
        sample.status = "processing"
        return sample

    def mark_analysed(self, sample: Sample) -> Sample:
        sample.status = "analysed"
        return sample

    def track(self, sample_id: str, samples: List[Sample]) -> Sample | None:
        return next((s for s in samples if s.sample_id == sample_id), None)


class ResultService:
    """Lab result management and anomaly monitoring."""

    def unreleased_abnormal(self, results: List[LabResult]) -> List[LabResult]:
        return [r for r in results if r.flag_abnormal and not r.released]

    def all_released(self, results: List[LabResult]) -> bool:
        return all(r.released for r in results)

    def pending_verification(self, results: List[LabResult]) -> List[LabResult]:
        return [r for r in results if not r.released and r.verified_by is None]
