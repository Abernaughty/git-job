#!/usr/bin/env python3
"""
Test scrape - runs a quick end-to-end test of the scraping pipeline.
Only scrapes active companies from the database.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from database.connection import get_db_connection
from models.company import get_active_companies, Company
from scrapers.greenhouse import GreenhouseScraper
from scrapers.lever import LeverScraper


async def test_scrape(limit_companies: int = 5):
    """
    Run a test scrape on a subset of active companies.
    
    Args:
        limit_companies: Max number of companies to scrape
    """
    print("=" * 60)
    print("🧪 TEST SCRAPE - End-to-End Verification")
    print("=" * 60)
    
    # Get active companies
    companies = get_active_companies()
    print(f"\n📊 Found {len(companies)} active companies in database")
    
    # Split by ATS platform
    greenhouse_companies = [c for c in companies if c.ats_platform == 'greenhouse']
    lever_companies = [c for c in companies if c.ats_platform == 'lever']
    
    print(f"   - Greenhouse: {len(greenhouse_companies)}")
    print(f"   - Lever: {len(lever_companies)}")
    
    # Limit for testing
    test_greenhouse = greenhouse_companies[:min(limit_companies, len(greenhouse_companies))]
    test_lever = lever_companies[:min(2, len(lever_companies))]  # Test at least some Lever
    
    print(f"\n🔬 Testing with {len(test_greenhouse)} Greenhouse + {len(test_lever)} Lever companies")
    
    total_jobs = 0
    results = []
    
    # Test Greenhouse companies
    print("\n" + "-" * 60)
    print("🏢 GREENHOUSE COMPANIES")
    print("-" * 60)
    
    async with GreenhouseScraper() as scraper:
        for company in test_greenhouse:
            if not company.ats_slug:
                print(f"  ⚠️ {company.name}: No ATS slug configured")
                results.append({
                    'company': company.name,
                    'platform': 'greenhouse',
                    'jobs': 0,
                    'status': 'error',
                    'error': 'No ATS slug'
                })
                continue
            try:
                jobs = await scraper.get_job_listings(company.ats_slug)
                count = len(jobs)
                total_jobs += count
                status = "✅" if count > 0 else "⚠️"
                print(f"  {status} {company.name}: {count} jobs")
                results.append({
                    'company': company.name,
                    'platform': 'greenhouse',
                    'jobs': count,
                    'status': 'ok' if count > 0 else 'empty'
                })
            except Exception as e:
                print(f"  ❌ {company.name}: Error - {str(e)[:50]}")
                results.append({
                    'company': company.name,
                    'platform': 'greenhouse',
                    'jobs': 0,
                    'status': 'error',
                    'error': str(e)
                })
    
    # Test Lever companies
    print("\n" + "-" * 60)
    print("🏢 LEVER COMPANIES")
    print("-" * 60)
    
    async with LeverScraper() as scraper:
        for company in test_lever:
            if not company.ats_slug:
                print(f"  ⚠️ {company.name}: No ATS slug configured")
                results.append({
                    'company': company.name,
                    'platform': 'lever',
                    'jobs': 0,
                    'status': 'error',
                    'error': 'No ATS slug'
                })
                continue
            try:
                jobs = await scraper.get_job_listings(company.ats_slug)
                count = len(jobs)
                total_jobs += count
                status = "✅" if count > 0 else "⚠️"
                print(f"  {status} {company.name}: {count} jobs")
                results.append({
                    'company': company.name,
                    'platform': 'lever',
                    'jobs': count,
                    'status': 'ok' if count > 0 else 'empty'
                })
            except Exception as e:
                print(f"  ❌ {company.name}: Error - {str(e)[:50]}")
                results.append({
                    'company': company.name,
                    'platform': 'lever',
                    'jobs': 0,
                    'status': 'error',
                    'error': str(e)
                })
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 60)
    
    success_count = len([r for r in results if r['status'] in ('ok', 'empty')])
    error_count = len([r for r in results if r['status'] == 'error'])
    
    print(f"\n  Companies tested: {len(results)}")
    print(f"  ✅ Successful: {success_count}")
    print(f"  ❌ Errors: {error_count}")
    print(f"  📝 Total jobs found: {total_jobs}")
    
    # Sample job data
    print("\n" + "-" * 60)
    print("📋 TOP COMPANIES BY JOB COUNT:")
    print("-" * 60)
    
    sorted_results = sorted(results, key=lambda x: x['jobs'], reverse=True)
    for r in sorted_results[:10]:
        print(f"  {r['company']}: {r['jobs']} jobs ({r['platform']})")
    
    print("\n✅ Test scrape complete!")
    
    return results


async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test the scraping pipeline")
    parser.add_argument(
        '--companies',
        type=int,
        default=5,
        help="Number of Greenhouse companies to test (default: 5)"
    )
    
    args = parser.parse_args()
    
    await test_scrape(limit_companies=args.companies)


if __name__ == "__main__":
    asyncio.run(main())
