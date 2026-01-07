from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Application:
    id: int
    status: str
    company: Optional[str]
    title: Optional[str]
    url: Optional[str]
