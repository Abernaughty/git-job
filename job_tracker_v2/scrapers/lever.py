"""
Lever ATS scraper.

Lever provides a public JSON API for job postings:
- List jobs: https://api.lever.co/v0/postings/{company}
- Job details: https://api.lever.co/v0/postings/{company}/{posting_id}

No authentication required for public postings.
"""

from datetime import datetime
from typing import Optional

import structlog
from bs4 import BeautifulSoup

from scrapers.base import BaseScraper

logger = structlog.get_logger()


class LeverScraper(BaseScraper):
    """Scraper for Lever job postings."""
    
    SOURCE_SITE = "lever"
    BASE_URL = "https://api.lever.co/v0/postings"
    
    async def get_job_listings(self, company_slug: str) -> list[dict]:
        """
        Get all job listings for a company from Lever API.
        
        Args:
            company_slug: Company identifier (e.g., 'netflix', 'databricks').
        
        Returns:
            List of job dictionaries from the API.
        """
        # Must include mode=json to get JSON response (default is HTML)
        url = f"{self.BASE_URL}/{company_slug}?mode=json"
        
        try:
            data = await self._fetch_json(url)
            
            # Lever returns a list directly
            if isinstance(data, list):
                return data
            return []
            
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
        
        Note: For Lever, the main listing endpoint usually includes all details,
        but this method exists for compatibility and edge cases.
        
        Args:
            job_id: Lever posting ID.
            company_slug: Company identifier.
        
        Returns:
            Job details dictionary.
        """
        url = f"{self.BASE_URL}/{company_slug}/{job_id}"
        
        try:
            data = await self._fetch_json(url)
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
        Extract standardized job data from Lever API response.
        
        Lever API response structure:
        {
            "id": "abc123-def456",
            "text": "Software Engineer",
            "categories": {
                "location": "San Francisco, CA",
                "team": "Engineering",
                "commitment": "Full-time"
            },
            "createdAt": 1705312800000,  # Unix timestamp in milliseconds
            "hostedUrl": "https://jobs.lever.co/company/abc123",
            "applyUrl": "https://jobs.lever.co/company/abc123/apply",
            "description": "Job description text...",
            "descriptionPlain": "Plain text description...",
            "lists": [
                {"text": "What you'll do", "content": "<li>Build features</li>..."},
                {"text": "Requirements", "content": "<li>5+ years</li>..."}
            ],
            "additional": "Additional info...",
            "additionalPlain": "Plain text additional...",
        }
        """
        job_id = raw_job.get("id", "")
        title = raw_job.get("text", "Unknown Title")
        
        # Categories contain location, team, commitment info
        categories = raw_job.get("categories", {})
        location = categories.get("location")
        team = categories.get("team")
        commitment = categories.get("commitment")  # Full-time, Part-time, Contract, etc.
        
        # URL - use provided or construct
        url = raw_job.get("hostedUrl")
        if not url:
            url = f"https://jobs.lever.co/{company_slug}/{job_id}"
        
        # Date parsing - Lever uses Unix timestamp in milliseconds
        posted_date = None
        created_at = raw_job.get("createdAt")
        if created_at:
            try:
                # Convert milliseconds to seconds
                dt = datetime.fromtimestamp(created_at / 1000)
                posted_date = dt.date().isoformat()
            except (ValueError, TypeError, OSError):
                pass
        
        # Description - combine description and lists content
        description_parts = []
        
        # Plain text description if available
        desc_plain = raw_job.get("descriptionPlain") or raw_job.get("description")
        if desc_plain:
            # Clean HTML if necessary
            if "<" in desc_plain:
                soup = BeautifulSoup(desc_plain, "lxml")
                desc_plain = soup.get_text(separator="\n", strip=True)
            description_parts.append(desc_plain)
        
        # Process lists (Requirements, Responsibilities, etc.)
        lists = raw_job.get("lists", [])
        for item in lists:
            section_title = item.get("text", "")
            section_content = item.get("content", "")
            if section_content:
                # Clean HTML
                soup = BeautifulSoup(section_content, "lxml")
                clean_content = soup.get_text(separator="\n", strip=True)
                if section_title:
                    description_parts.append(f"\n{section_title}:\n{clean_content}")
                else:
                    description_parts.append(clean_content)
        
        # Additional info
        additional = raw_job.get("additionalPlain") or raw_job.get("additional")
        if additional:
            if "<" in additional:
                soup = BeautifulSoup(additional, "lxml")
                additional = soup.get_text(separator="\n", strip=True)
            description_parts.append(f"\nAdditional Information:\n{additional}")
        
        description = "\n".join(description_parts) if description_parts else None
        
        return {
            "source_url": url,
            "external_id": job_id,
            "raw_title": title,
            "raw_description": description,
            "location_raw": location,
            "posted_date": posted_date,
            "department": team,
            "commitment": commitment,  # Extra field for Lever
        }


async def test_lever_scraper():
    """Quick test of the Lever scraper with a real company."""
    
    async with LeverScraper() as scraper:
        # Test with a company known to use Lever
        jobs = await scraper.get_job_listings("netflix")
        print(f"\nFound {len(jobs)} jobs at Netflix")
        
        if jobs:
            # Get details for the first job
            first_job = jobs[0]
            print(f"\nFirst job: {first_job.get('text')}")
            
            categories = first_job.get("categories", {})
            print(f"Location: {categories.get('location')}")
            print(f"Team: {categories.get('team')}")
            
            # Extract data
            extracted = scraper.extract_job_data(first_job, "netflix")
            print(f"\nExtracted data:")
            for key, value in extracted.items():
                if key == "raw_description":
                    print(f"  {key}: {value[:200] if value else None}...")
                else:
                    print(f"  {key}: {value}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_lever_scraper())
