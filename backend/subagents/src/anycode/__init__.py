"""
anycode — Iryax Multi-Product AI Agent Platform.

Public entry point. Import product agents directly from their packages or
use the shared registry to look them up by product ID.

    from anycode.agents.products.registry import REGISTRY
    agent = REGISTRY["iryax.recruitment"]
"""
from __future__ import annotations

from anycode.agents.products import registry  # noqa: F401 — keeps registry importable

__all__ = ["registry"]
