"""
Greenhouse ATS scraper.

Greenhouse provides a public JSON API for job boards:
- List jobs: https://boards-api.greenhouse.io/v1/boards/{company}/jobs
- Job details: https://boards-api.greenhouse.io/v1/boards/{company}/jobs/{job_id}

No authentication required.
"""

from datetime import datetime
from typing import Optional

import structlog
from bs4 import BeautifulSoup

from scrapers.base import BaseScraper

logger = structlog.get_logger()


class GreenhouseScraper(BaseScraper):
    """Scraper for Greenhouse job boards."""
    
    SOURCE_SITE = "greenhouse"
    BASE_URL = "https://boards-api.greenhouse.io/v1/boards"
    
    async def get_job_listings(self, company_slug: str) -> list[dict]:
        """
        Get all job listings for a company from Greenhouse API.
        
        Args:
            company_slug: Company identifier (e.g., 'airbnb', 'stripe').
        
        Returns:
            List of job dictionaries from the API.
        """
        url = f"{self.BASE_URL}/{company_slug}/jobs"
        
        try:
            data = await self._fetch_json(url)
            
            # Greenhouse returns {"jobs": [...]}
            if isinstance(data, dict):
                jobs = data.get("jobs", [])
            else:
                jobs = data  # Handle unexpected list response
            return jobs
            
        except Exception as e:
            self.logger.error(
                "Failed to get job listings",
                company=company_slug,
                error=str(e),
            )
            raise
    
    async def get_job_details(self, job_id: str, company_slug: str) -> Optional[dict]:
        """
        Get detailed information for a specific job.
        
        Args:
            job_id: Greenhouse job ID.
            company_slug: Company identifier.
        
        Returns:
            Job details dictionary with full description.
        """
        url = f"{self.BASE_URL}/{company_slug}/jobs/{job_id}"
        
        try:
            data = await self._fetch_json(url)
            # Greenhouse job details endpoint returns a dict
            if isinstance(data, dict):
                return data
            return None
            
        except Exception as e:
            self.logger.warning(
                "Failed to get job details",
                company=company_slug,
                job_id=job_id,
                error=str(e),
            )
            return None
    
    def extract_job_data(self, raw_job: dict, company_slug: str) -> dict:
        """
        Extract standardized job data from Greenhouse API response.
        
        Greenhouse API response structure:
        {
            "id": 123456,
            "title": "Software Engineer",
            "location": {"name": "San Francisco, CA"},
            "updated_at": "2024-01-15T10:30:00-05:00",
            "absolute_url": "https://boards.greenhouse.io/company/jobs/123456",
            "content": "<p>Job description HTML...</p>",  # Only in details endpoint
            "departments": [{"name": "Engineering"}],
            "offices": [{"name": "San Francisco"}],
        }
        """
        job_id = str(raw_job.get("id", ""))
        title = raw_job.get("title", "Unknown Title")
        
        # Location handling
        location = raw_job.get("location", {})
        location_name = location.get("name") if isinstance(location, dict) else str(location) if location else None
        
        # URL - use provided or construct
        url = raw_job.get("absolute_url")
        if not url:
            url = f"https://boards.greenhouse.io/{company_slug}/jobs/{job_id}"
        
        # Date parsing
        posted_date = None
        date_str = raw_job.get("updated_at") or raw_job.get("created_at")
        if date_str:
            try:
                # Greenhouse uses ISO format with timezone
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                posted_date = dt.date().isoformat()
            except (ValueError, AttributeError):
                pass
        
        # Description - clean HTML if present
        description = None
        content = raw_job.get("content")
        if content:
            # Strip HTML tags for plain text storage
            soup = BeautifulSoup(content, "lxml")
            description = soup.get_text(separator="\n", strip=True)
        
        # Department info
        departments = raw_job.get("departments", [])
        department = departments[0].get("name") if departments else None
        
        return {
            "source_url": url,
            "external_id": job_id,
            "raw_title": title,
            "raw_description": description,
            "location_raw": location_name,
            "posted_date": posted_date,
            "department": department,
        }


async def test_greenhouse_scraper():
    """Quick test of the Greenhouse scraper with a real company."""
    import asyncio
    
    async with GreenhouseScraper() as scraper:
        # Test with a company known to use Greenhouse
        jobs = await scraper.get_job_listings("anthropic")
        print(f"\nFound {len(jobs)} jobs at Anthropic")
        
        if jobs:
            # Get details for the first job
            first_job = jobs[0]
            print(f"\nFirst job: {first_job.get('title')}")
            print(f"Location: {first_job.get('location', {}).get('name')}")
            
            # Get full details
            job_id = first_job.get("id")
            if job_id:
                details = await scraper.get_job_details(str(job_id), "anthropic")
                if details:
                    extracted = scraper.extract_job_data(details, "anthropic")
                    print(f"\nExtracted data:")
                    for key, value in extracted.items():
                        if key == "raw_description":
                            print(f"  {key}: {value[:200] if value else None}...")
                        else:
                            print(f"  {key}: {value}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_greenhouse_scraper())
