"""
Base scraper class with HTTP client, rate limiting, and retry logic.
"""

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import httpx
import structlog
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from config.settings import settings

logger = structlog.get_logger()


@dataclass
class ScraperResult:
    """Result from a scraping operation."""
    
    company_name: str
    company_id: int
    source_site: str
    jobs_found: int = 0
    jobs_new: int = 0
    jobs_updated: int = 0
    success: bool = True
    error_message: Optional[str] = None
    duration_seconds: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    
    def __str__(self) -> str:
        status = "✓" if self.success else "✗"
        return f"{status} {self.company_name}: {self.jobs_found} found, {self.jobs_new} new ({self.duration_seconds:.1f}s)"


class RateLimiter:
    """
    Simple rate limiter that tracks last request time per domain.
    Ensures minimum delay between requests to the same domain.
    """
    
    def __init__(self, min_delay: float = 1.5):
        self.min_delay = min_delay
        self._last_request: dict[str, float] = {}
        self._lock = asyncio.Lock()
    
    async def acquire(self, domain: str) -> None:
        """Wait if necessary to respect rate limits."""
        async with self._lock:
            now = time.time()
            last = self._last_request.get(domain, 0)
            elapsed = now - last
            
            if elapsed < self.min_delay:
                wait_time = self.min_delay - elapsed
                logger.debug("Rate limiting", domain=domain, wait_seconds=wait_time)
                await asyncio.sleep(wait_time)
            
            self._last_request[domain] = time.time()


# Global rate limiter instance
rate_limiter = RateLimiter(min_delay=settings.scrape_delay_seconds)


class BaseScraper(ABC):
    """
    Abstract base class for job scrapers.
    Provides HTTP client with rate limiting and retry logic.
    """
    
    # Subclasses should override these
    SOURCE_SITE: str = "unknown"
    BASE_URL: str = ""
    
    def __init__(self):
        self.client: Optional[httpx.AsyncClient] = None
        self.logger = structlog.get_logger().bind(scraper=self.SOURCE_SITE)
    
    async def __aenter__(self):
        """Create async HTTP client on context entry."""
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.scrape_timeout_seconds),
            headers={
                "User-Agent": settings.scrape_user_agent,
                "Accept": "application/json",
            },
            follow_redirects=True,
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close HTTP client on context exit."""
        if self.client:
            await self.client.aclose()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        before_sleep=lambda retry_state: logger.warning(
            "Retrying request",
            attempt=retry_state.attempt_number,
            wait=getattr(retry_state.next_action, 'sleep', 0) if retry_state.next_action else 0,
        ),
    )
    async def _fetch_json(self, url: str) -> dict | list:
        """
        Fetch JSON from URL with rate limiting and retry.
        
        Args:
            url: Full URL to fetch.
        
        Returns:
            Parsed JSON response.
        
        Raises:
            httpx.HTTPStatusError: On 4xx/5xx responses.
            httpx.TimeoutException: On timeout (will be retried).
        """
        if not self.client:
            raise RuntimeError("Scraper must be used as async context manager")
        
        # Extract domain for rate limiting
        domain = httpx.URL(url).host
        await rate_limiter.acquire(domain)
        
        self.logger.debug("Fetching", url=url)
        
        response = await self.client.get(url)
        response.raise_for_status()
        
        return response.json()
    
    async def _fetch_html(self, url: str) -> str:
        """
        Fetch HTML content from URL with rate limiting and retry.
        
        Args:
            url: Full URL to fetch.
        
        Returns:
            HTML content as string.
        """
        if not self.client:
            raise RuntimeError("Scraper must be used as async context manager")
        
        domain = httpx.URL(url).host
        await rate_limiter.acquire(domain)
        
        self.logger.debug("Fetching HTML", url=url)
        
        response = await self.client.get(url)
        response.raise_for_status()
        
        return response.text
    
    @abstractmethod
    async def get_job_listings(self, company_slug: str) -> list[dict]:
        """
        Get all job listings for a company.
        
        Args:
            company_slug: Company identifier in the ATS URL.
        
        Returns:
            List of raw job data dictionaries.
        """
        pass
    
    @abstractmethod
    async def get_job_details(self, job_id: str, company_slug: str) -> Optional[dict]:
        """
        Get detailed information for a specific job.
        
        Args:
            job_id: Job identifier.
            company_slug: Company identifier.
        
        Returns:
            Job details dictionary, or None if not found.
        """
        pass
    
    @abstractmethod
    def extract_job_data(self, raw_job: dict, company_slug: str) -> dict:
        """
        Extract standardized job data from raw API response.
        
        Args:
            raw_job: Raw job data from API.
            company_slug: Company identifier.
        
        Returns:
            Standardized job data dictionary with keys:
            - source_url: str
            - external_id: str
            - raw_title: str
            - raw_description: str (optional)
            - location_raw: str (optional)
            - posted_date: str (optional, ISO format)
        """
        pass
    
    async def scrape_company(self, company_id: int, company_slug: str, company_name: str) -> ScraperResult:
        """
        Scrape all jobs for a company and return results.
        
        Args:
            company_id: Database ID of the company.
            company_slug: ATS slug for the company.
            company_name: Company name for logging.
        
        Returns:
            ScraperResult with statistics.
        """
        start_time = time.time()
        result = ScraperResult(
            company_name=company_name,
            company_id=company_id,
            source_site=self.SOURCE_SITE,
        )
        
        try:
            self.logger.info("Scraping company", company=company_name, slug=company_slug)
            
            # Get job listings
            jobs = await self.get_job_listings(company_slug)
            result.jobs_found = len(jobs)
            
            self.logger.info(
                "Found jobs",
                company=company_name,
                count=len(jobs),
            )
            
            # Process each job
            for raw_job in jobs:
                try:
                    job_data = self.extract_job_data(raw_job, company_slug)
                    
                    # Check if we need full details
                    if not job_data.get("raw_description"):
                        job_id = job_data.get("external_id")
                        if job_id:
                            details = await self.get_job_details(job_id, company_slug)
                            if details:
                                detailed_data = self.extract_job_data(details, company_slug)
                                job_data.update(detailed_data)
                    
                    # Save to database
                    from models.posting import (
                        Posting,
                        save_posting,
                        posting_exists,
                        update_last_seen,
                    )
                    
                    source_url = job_data["source_url"]
                    
                    if posting_exists(source_url):
                        update_last_seen(source_url)
                        result.jobs_updated += 1
                    else:
                        posting = Posting(
                            company_id=company_id,
                            source_url=source_url,
                            source_site=self.SOURCE_SITE,
                            external_id=job_data.get("external_id"),
                            raw_title=job_data["raw_title"],
                            raw_description=job_data.get("raw_description"),
                            location_raw=job_data.get("location_raw"),
                            posted_date=job_data.get("posted_date"),
                        )
                        save_posting(posting)
                        result.jobs_new += 1
                        
                except Exception as e:
                    self.logger.warning(
                        "Error processing job",
                        company=company_name,
                        error=str(e),
                    )
                    continue
            
        except httpx.HTTPStatusError as e:
            result.success = False
            result.error_message = f"HTTP {e.response.status_code}: {e.response.reason_phrase}"
            self.logger.error(
                "HTTP error",
                company=company_name,
                status=e.response.status_code,
            )
        except Exception as e:
            result.success = False
            result.error_message = str(e)
            self.logger.error(
                "Scraping error",
                company=company_name,
                error=str(e),
            )
        
        result.duration_seconds = time.time() - start_time
        return result
