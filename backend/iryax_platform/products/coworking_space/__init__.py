"""Coworking Space product agent package."""

from iryax_platform.products.coworking_space.agent import CoworkingSpaceAgent
from iryax_platform.products.coworking_space.schemas import (
    BookingConfirmation,
    BookingProposal,
    FacilityRequest,
    SpaceUnit,
    VisitorPass,
)
from iryax_platform.products.coworking_space.service import CoworkingSpaceService

__all__ = [
    "CoworkingSpaceAgent",
    "BookingConfirmation",
    "BookingProposal",
    "FacilityRequest",
    "SpaceUnit",
    "VisitorPass",
    "CoworkingSpaceService",
]
