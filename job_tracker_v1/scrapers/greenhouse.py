from __future__ import annotations

from typing import Optional

from .base import BaseScraper, ScrapedJob


class GreenhouseScraper(BaseScraper):
    @property
    def source_name(self) -> str:
        return "greenhouse"

    def search(
        self,
        keywords: str,
        location: Optional[str] = None,
        **filters: str,
    ) -> list[ScrapedJob]:
        raise NotImplementedError

    def get_job_details(self, job_url: str) -> ScrapedJob:
        raise NotImplementedError
