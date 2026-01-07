from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ExperienceRange:
    minimum: Optional[int]
    maximum: Optional[int]


def extract_experience(text: str) -> ExperienceRange:
    """Parse experience requirement from text. TODO: implement."""
    return ExperienceRange(None, None)
