#!/usr/bin/env python3
"""
Test all Greenhouse company slugs from companies_seed.json to see which ones work.
"""

import asyncio
import json
from pathlib import Path

import httpx


async def test_greenhouse_slug(client: httpx.AsyncClient, company_name: str, slug: str) -> tuple[str, str, int, str]:
    """
    Test if a Greenhouse slug returns valid job postings.
    
    Returns:
        Tuple of (company_name, slug, job_count, status)
    """
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    
    try:
        response = await client.get(url)
        
        if response.status_code == 200:
            data = response.json()
            jobs = data.get("jobs", [])
            return (company_name, slug, len(jobs), "✅ WORKING")
        elif response.status_code == 404:
            return (company_name, slug, 0, "❌ 404 Not Found")
        else:
            return (company_name, slug, 0, f"❌ HTTP {response.status_code}")
            
    except Exception as e:
        return (company_name, slug, 0, f"❌ Error: {str(e)[:50]}")


async def main():
    # Load companies from seed file
    seed_path = Path(__file__).parent.parent / "config" / "companies_seed.json"
    
    with open(seed_path) as f:
        data = json.load(f)
    
    # Filter Greenhouse companies
    greenhouse_companies = [
        c for c in data["companies"]
        if c.get("ats_platform") == "greenhouse"
    ]
    
    print(f"\n🔍 Testing {len(greenhouse_companies)} Greenhouse companies...\n")
    print("-" * 70)
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Test each company with a small delay to be respectful
        results = []
        
        for company in greenhouse_companies:
            result = await test_greenhouse_slug(
                client,
                company["name"],
                company["ats_slug"],
            )
            results.append(result)
            
            # Print result immediately
            name, slug, count, status = result
            if "WORKING" in status:
                print(f"{status} {name:25} ({slug:20}) - {count:4} jobs")
            else:
                print(f"{status} {name:25} ({slug:20})")
            
            # Small delay to avoid rate limiting
            await asyncio.sleep(0.3)
    
    # Summary
    print("-" * 70)
    working = [r for r in results if "WORKING" in r[3]]
    broken = [r for r in results if "WORKING" not in r[3]]
    
    print(f"\n📊 Summary:")
    print(f"   ✅ Working: {len(working)}/{len(results)}")
    print(f"   ❌ Broken:  {len(broken)}/{len(results)}")
    
    if working:
        total_jobs = sum(r[2] for r in working)
        print(f"   📝 Total jobs from working APIs: {total_jobs}")
        
        print(f"\n✅ Working Greenhouse companies:")
        for name, slug, count, _ in sorted(working, key=lambda x: -x[2]):
            print(f"   {name}: {count} jobs")
    
    if broken:
        print(f"\n❌ Broken Greenhouse slugs (need verification):")
        for name, slug, _, status in broken:
            print(f"   {name} ({slug}): {status}")


if __name__ == "__main__":
    asyncio.run(main())
