"""
anycode.agents — Iryax product agent sub-package.

All 7 product agents live under anycode.agents.products.<product_name>.
"""
from __future__ import annotations

from anycode.agents.products import registry  # noqa: F401

__all__ = ["registry"]
