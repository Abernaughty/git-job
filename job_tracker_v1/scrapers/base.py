from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class ScrapedJob:
    """Standardized job data returned by all scrapers."""

    external_id: str
    source: str
    url: str
    title: str
    company: str
    location: Optional[str]
    salary_raw: Optional[str]
    description_raw: str
    job_type: Optional[str]
    date_posted: Optional[str]


class BaseScraper(ABC):
    """Abstract base class that all site-specific scrapers must implement."""

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Unique identifier for this source (e.g., 'indeed')."""
        raise NotImplementedError

    @abstractmethod
    def search(
        self,
        keywords: str,
        location: Optional[str] = None,
        **filters: str,
    ) -> list[ScrapedJob]:
        """
        Run a search and return all matching jobs.
        Handles pagination internally.
        """
        raise NotImplementedError

    @abstractmethod
    def get_job_details(self, job_url: str) -> ScrapedJob:
        """Fetch full details for a single job listing."""
        raise NotImplementedError
