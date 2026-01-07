"""
Scraper orchestration service.

Manages scraping across all companies, handles concurrency,
and logs results to the database.
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import structlog

from config.settings import settings
from models.company import Company, get_active_companies, update_last_scraped
from scrapers.base import ScraperResult
from scrapers.greenhouse import GreenhouseScraper
from scrapers.lever import LeverScraper
from database.connection import get_db_connection

logger = structlog.get_logger()


@dataclass
class ScrapeRunSummary:
    """Summary of a complete scrape run across all companies."""
    
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    companies_total: int = 0
    companies_success: int = 0
    companies_failed: int = 0
    jobs_found_total: int = 0
    jobs_new_total: int = 0
    jobs_updated_total: int = 0
    duration_seconds: float = 0.0
    results: list[ScraperResult] = field(default_factory=list)
    
    def __str__(self) -> str:
        return (
            f"Scrape Run Summary:\n"
            f"  Companies: {self.companies_success}/{self.companies_total} successful\n"
            f"  Jobs Found: {self.jobs_found_total}\n"
            f"  Jobs New: {self.jobs_new_total}\n"
            f"  Jobs Updated: {self.jobs_updated_total}\n"
            f"  Duration: {self.duration_seconds:.1f}s"
        )


def log_scrape_result(result: ScraperResult) -> None:
    """Log a scrape result to the scrape_log table."""
    with get_db_connection() as conn:
        conn.execute("""
            INSERT INTO scrape_log (
                source_site, company_id, started_at, completed_at,
                status, postings_found, postings_new, postings_updated,
                error_message, duration_seconds
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            result.source_site,
            result.company_id,
            result.timestamp.isoformat(),
            datetime.now().isoformat(),
            "success" if result.success else "failed",
            result.jobs_found,
            result.jobs_new,
            result.jobs_updated,
            result.error_message,
            result.duration_seconds,
        ))


async def scrape_company(company: Company) -> ScraperResult:
    """
    Scrape a single company using the appropriate scraper.
    
    Args:
        company: Company to scrape.
    
    Returns:
        ScraperResult with statistics.
    """
    # Choose scraper based on ATS platform
    if company.ats_platform == "greenhouse":
        scraper_class = GreenhouseScraper
    elif company.ats_platform == "lever":
        scraper_class = LeverScraper
    else:
        # Unknown platform - return error result
        return ScraperResult(
            company_name=company.name,
            company_id=company.id or 0,
            source_site=company.ats_platform or "unknown",
            success=False,
            error_message=f"Unsupported ATS platform: {company.ats_platform}",
        )
    
    async with scraper_class() as scraper:
        result = await scraper.scrape_company(
            company_id=company.id or 0,
            company_slug=company.ats_slug or "",
            company_name=company.name,
        )
    
    # Update last_scraped_at on success
    if result.success and company.id:
        update_last_scraped(company.id)
    
    # Log result to database
    log_scrape_result(result)
    
    return result


async def scrape_companies(
    companies: list[Company],
    max_concurrent: int = 3,
) -> list[ScraperResult]:
    """
    Scrape multiple companies with controlled concurrency.
    
    Args:
        companies: List of companies to scrape.
        max_concurrent: Maximum concurrent scrape operations.
    
    Returns:
        List of ScraperResult objects.
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def scrape_with_semaphore(company: Company) -> ScraperResult:
        async with semaphore:
            return await scrape_company(company)
    
    tasks = [scrape_with_semaphore(company) for company in companies]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Convert exceptions to error results
    processed_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            company = companies[i]
            processed_results.append(ScraperResult(
                company_name=company.name,
                company_id=company.id or 0,
                source_site=company.ats_platform or "unknown",
                success=False,
                error_message=str(result),
            ))
        else:
            processed_results.append(result)
    
    return processed_results


async def run_full_scrape(
    ats_platform: Optional[str] = None,
    max_concurrent: Optional[int] = None,
) -> ScrapeRunSummary:
    """
    Run a full scrape across all active companies.
    
    Args:
        ats_platform: Optional filter to scrape only 'greenhouse' or 'lever'.
        max_concurrent: Max concurrent scrapers (default from settings).
    
    Returns:
        ScrapeRunSummary with aggregate statistics.
    """
    start_time = time.time()
    summary = ScrapeRunSummary()
    
    # Get active companies
    companies = get_active_companies(ats_platform)
    summary.companies_total = len(companies)
    
    if not companies:
        logger.warning("No companies to scrape", platform_filter=ats_platform)
        return summary
    
    logger.info(
        "Starting scrape run",
        companies=len(companies),
        platform_filter=ats_platform,
    )
    
    # Run scraping
    concurrent = max_concurrent or settings.scrape_max_concurrent or 3
    results = await scrape_companies(companies, max_concurrent=concurrent)
    
    # Aggregate results
    for result in results:
        summary.results.append(result)
        
        if result.success:
            summary.companies_success += 1
        else:
            summary.companies_failed += 1
        
        summary.jobs_found_total += result.jobs_found
        summary.jobs_new_total += result.jobs_new
        summary.jobs_updated_total += result.jobs_updated
        
        # Log individual result
        logger.info(str(result))
    
    summary.completed_at = datetime.now()
    summary.duration_seconds = time.time() - start_time
    
    logger.info(
        "Scrape run complete",
        companies_success=summary.companies_success,
        companies_failed=summary.companies_failed,
        jobs_found=summary.jobs_found_total,
        jobs_new=summary.jobs_new_total,
        duration_seconds=summary.duration_seconds,
    )
    
    return summary


async def scrape_single_company(company_name: str) -> Optional[ScraperResult]:
    """
    Scrape a single company by name.
    
    Args:
        company_name: Name of the company to scrape.
    
    Returns:
        ScraperResult, or None if company not found.
    """
    from models.company import get_company_by_name
    
    company = get_company_by_name(company_name)
    if not company:
        logger.warning("Company not found", company=company_name)
        return None
    
    if not company.is_active:
        logger.warning("Company is not active", company=company_name)
        return None
    
    return await scrape_company(company)


# CLI for testing
async def main():
    """CLI entry point for testing scraper service."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run job scrapers")
    parser.add_argument(
        "--platform",
        choices=["greenhouse", "lever"],
        help="Only scrape companies on this platform",
    )
    parser.add_argument(
        "--company",
        type=str,
        help="Scrape a single company by name",
    )
    parser.add_argument(
        "--concurrent",
        type=int,
        default=3,
        help="Maximum concurrent scrapers",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List companies that would be scraped without actually scraping",
    )
    
    args = parser.parse_args()
    
    if args.company:
        # Single company mode
        result = await scrape_single_company(args.company)
        if result:
            print(f"\n{result}")
        else:
            print(f"\nCompany '{args.company}' not found or not active")
    elif args.dry_run:
        # Dry run - just list companies
        companies = get_active_companies(args.platform)
        print(f"\nWould scrape {len(companies)} companies:")
        for c in companies:
            print(f"  {c.name} ({c.ats_platform}/{c.ats_slug})")
    else:
        # Full scrape
        summary = await run_full_scrape(
            ats_platform=args.platform,
            max_concurrent=args.concurrent,
        )
        print(f"\n{summary}")


if __name__ == "__main__":
    asyncio.run(main())
