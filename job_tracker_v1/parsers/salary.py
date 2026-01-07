from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class SalaryRange:
    minimum: Optional[int]
    maximum: Optional[int]


def extract_salary(text: str) -> SalaryRange:
    """Parse salary range from text. TODO: implement."""
    return SalaryRange(None, None)
