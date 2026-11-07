"""Validation of Home Assistant's visual MDI icon-picker values."""
from __future__ import annotations

import re


def validate_mdi_icon(value: str) -> str:
    """Allow only an MDI name, never HTML, URLs, external paths or custom data."""
    if not isinstance(value, str) or not re.fullmatch(
        r"mdi:[a-z][a-z0-9-]{0,79}", value
    ):
        raise ValueError("Invalid Material Design icon")
    return value
