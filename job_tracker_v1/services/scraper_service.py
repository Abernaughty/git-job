from __future__ import annotations

from typing import Any, Iterable, Optional, Type

from scrapers.base import BaseScraper, ScrapedJob
from scrapers.greenhouse import GreenhouseScraper
from scrapers.indeed import IndeedScraper
from models.database import initialize_db
from models.job import upsert_job


class ScraperService:
    """Orchestrate scraping across configured sources."""

    def __init__(
        self,
        db_path: str,
        searches: Iterable[dict[str, Any]],
        scraper_registry: Optional[dict[str, Type[BaseScraper]]] = None,
    ) -> None:
        self._db_path = db_path
        self._searches = list(searches)
        self._registry = scraper_registry or {
            "indeed": IndeedScraper,
            "greenhouse": GreenhouseScraper,
        }

    def run(self, search_name: str | None = None) -> list[ScrapedJob]:
        conn = initialize_db(self._db_path)
        scraped: list[ScrapedJob] = []
        for search in self._searches:
            if search_name and search.get("name") != search_name:
                continue
            sites = search.get("sites", [])
            keywords = search.get("keywords", "")
            location = search.get("location")
            filters = search.get("filters", {})
            for site in sites:
                scraper_cls = self._registry.get(site)
                if not scraper_cls:
                    print(f"Skipping unknown site '{site}'")
                    continue
                scraper = scraper_cls()
                try:
                    results = scraper.search(
                        keywords=keywords,
                        location=location,
                        **filters,
                    )
                except NotImplementedError:
                    print(f"Scraper for '{site}' not implemented yet")
                    continue
                for job in results:
                    upsert_job(conn, self._to_job_data(job))
                scraped.extend(results)
        conn.close()
        return scraped

    @staticmethod
    def _to_job_data(job: ScrapedJob) -> dict[str, Any]:
        return {
            "external_id": job.external_id,
            "source": job.source,
            "url": job.url,
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "salary_raw": job.salary_raw,
            "description_raw": job.description_raw,
            "job_type": job.job_type,
            "date_posted": job.date_posted,
        }
