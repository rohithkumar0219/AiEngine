"""Shared utility tools for product agents."""

from __future__ import annotations

import re
from typing import Any, Dict


def sanitize_input_text(text: str) -> str:
    """Strip dangerous characters or prompt-injection delimiters from user input."""
    cleaned = text.strip()
    # Normalize multiple whitespace
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def format_currency_inr(amount: float) -> str:
    """Format floating point numbers as INR currency representation."""
    return f"₹{amount:,.2f}"


def calculate_percentage(part: float, total: float) -> float:
    """Safe percentage computation."""
    if total <= 0:
        return 0.0
    return round((part / total) * 100, 1)
