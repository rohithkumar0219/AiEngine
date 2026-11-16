"""Medical Camps product agent package."""

from iryax_platform.products.medical_camps.agent import MedicalCampsAgent
from iryax_platform.products.medical_camps.schemas import (
    AggregateCampReport,
    CampPlan,
    PatientRegistration,
    ResourceInventory,
    VitalValidation,
)
from iryax_platform.products.medical_camps.service import MedicalCampsService

__all__ = [
    "MedicalCampsAgent",
    "AggregateCampReport",
    "CampPlan",
    "PatientRegistration",
    "ResourceInventory",
    "VitalValidation",
    "MedicalCampsService",
]
