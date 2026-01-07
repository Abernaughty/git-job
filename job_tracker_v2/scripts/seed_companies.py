"""
Load seed companies from the companies_seed.json file.
"""

import json
import sys
from pathlib import Path
from typing import Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from database.connection import init_database, get_db_connection
from models.company import Company, save_company, get_company_by_name, count_companies
from config.settings import CONFIG_DIR


def load_seed_companies(seed_file: Optional[Path] = None, skip_existing: bool = True) -> dict:
    """
    Load companies from the seed JSON file into the database.
    
    Args:
        seed_file: Path to the seed JSON file. Defaults to config/companies_seed.json.
        skip_existing: If True, skip companies that already exist by name.
    
    Returns:
        Dictionary with counts: {'added': N, 'skipped': N, 'errors': N}
    """
    seed_path = seed_file or CONFIG_DIR / "companies_seed.json"
    
    if not seed_path.exists():
        raise FileNotFoundError(f"Seed file not found: {seed_path}")
    
    with open(seed_path, 'r') as f:
        data = json.load(f)
    
    companies_data = data.get('companies', [])
    
    results = {'added': 0, 'skipped': 0, 'errors': 0}
    
    for company_data in companies_data:
        name = company_data.get('name')
        if not name:
            print(f"  Skipping company with no name: {company_data}")
            results['errors'] += 1
            continue
        
        # Check if exists
        if skip_existing:
            existing = get_company_by_name(name)
            if existing:
                print(f"  Skipping existing: {name}")
                results['skipped'] += 1
                continue
        
        # Read is_active from seed data (default to True for backward compatibility)
        is_active = company_data.get('is_active', True)
        
        try:
            company = Company(
                name=name,
                website=company_data.get('website'),
                ats_platform=company_data.get('ats_platform'),
                ats_slug=company_data.get('ats_slug'),
                industry=company_data.get('industry'),
                size_bucket=company_data.get('size_bucket'),
                headquarters_location=company_data.get('headquarters_location'),
                notes=company_data.get('notes'),
                is_active=is_active,
            )
            save_company(company)
            status = "✅" if is_active else "⏸️"
            print(f"  {status} Added: {name} ({company.ats_platform}/{company.ats_slug}) [active={is_active}]")
            results['added'] += 1
        except Exception as e:
            print(f"  Error adding {name}: {e}")
            results['errors'] += 1
    
    return results


def main():
    """Main entry point for seed loading."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Load seed companies into database")
    parser.add_argument(
        '--seed-file',
        type=Path,
        default=None,
        help="Path to seed JSON file (default: config/companies_seed.json)"
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help="Replace existing companies (by default, existing are skipped)"
    )
    parser.add_argument(
        '--init-db',
        action='store_true',
        help="Initialize database before loading (creates tables if needed)"
    )
    
    args = parser.parse_args()
    
    # Initialize database if requested
    if args.init_db:
        print("Initializing database...")
        init_database()
    
    # Load seed companies
    print(f"\nLoading seed companies...")
    results = load_seed_companies(
        seed_file=args.seed_file,
        skip_existing=not args.force
    )
    
    # Print summary
    print(f"\n{'='*40}")
    print(f"Seed loading complete!")
    print(f"  Added: {results['added']}")
    print(f"  Skipped: {results['skipped']}")
    print(f"  Errors: {results['errors']}")
    print(f"  Total companies in database: {count_companies()}")


if __name__ == "__main__":
    main()
