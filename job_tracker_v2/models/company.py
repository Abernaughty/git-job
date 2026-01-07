"""
Company model and database operations.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import json

from database.connection import get_db_connection, row_to_dict, rows_to_dicts


@dataclass
class Company:
    """Represents a company with job postings to track."""
    
    id: Optional[int] = None
    name: str = ""
    website: Optional[str] = None
    careers_url: Optional[str] = None
    ats_platform: Optional[str] = None  # greenhouse, lever, workday, custom, unknown
    ats_slug: Optional[str] = None
    industry: Optional[str] = None
    size_bucket: Optional[str] = None  # startup, small, medium, large, enterprise
    headquarters_location: Optional[str] = None
    glassdoor_url: Optional[str] = None
    notes: Optional[str] = None
    is_active: bool = True
    custom_scrape_config: Optional[dict] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_scraped_at: Optional[datetime] = None
    
    @classmethod
    def from_row(cls, row) -> "Company":
        """Create a Company from a database row."""
        data = row_to_dict(row) if hasattr(row, 'keys') else dict(row)
        
        # Parse JSON fields
        if data.get('custom_scrape_config'):
            try:
                data['custom_scrape_config'] = json.loads(data['custom_scrape_config'])
            except (json.JSONDecodeError, TypeError):
                data['custom_scrape_config'] = None
        
        # Convert is_active to bool
        data['is_active'] = bool(data.get('is_active', 1))
        
        return cls(**data)
    
    @classmethod
    def from_dict(cls, data: dict) -> "Company":
        """Create a Company from a dictionary."""
        # Filter to only known fields
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)
    
    def to_dict(self) -> dict:
        """Convert Company to a dictionary."""
        data = {
            'id': self.id,
            'name': self.name,
            'website': self.website,
            'careers_url': self.careers_url,
            'ats_platform': self.ats_platform,
            'ats_slug': self.ats_slug,
            'industry': self.industry,
            'size_bucket': self.size_bucket,
            'headquarters_location': self.headquarters_location,
            'glassdoor_url': self.glassdoor_url,
            'notes': self.notes,
            'is_active': 1 if self.is_active else 0,
            'custom_scrape_config': json.dumps(self.custom_scrape_config) if self.custom_scrape_config else None,
        }
        return data
    
    @property
    def greenhouse_url(self) -> Optional[str]:
        """Generate Greenhouse job board URL."""
        if self.ats_platform == 'greenhouse' and self.ats_slug:
            return f"https://boards.greenhouse.io/{self.ats_slug}"
        return None
    
    @property
    def greenhouse_api_url(self) -> Optional[str]:
        """Generate Greenhouse API URL."""
        if self.ats_platform == 'greenhouse' and self.ats_slug:
            return f"https://boards-api.greenhouse.io/v1/boards/{self.ats_slug}/jobs"
        return None
    
    @property
    def lever_url(self) -> Optional[str]:
        """Generate Lever job board URL."""
        if self.ats_platform == 'lever' and self.ats_slug:
            return f"https://jobs.lever.co/{self.ats_slug}"
        return None


# Database operations

def save_company(company: Company) -> Company:
    """
    Insert or update a company in the database.
    
    Returns:
        Company with updated id (if new).
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        if company.id:
            # Update existing
            cursor.execute("""
                UPDATE companies SET
                    name = ?,
                    website = ?,
                    careers_url = ?,
                    ats_platform = ?,
                    ats_slug = ?,
                    industry = ?,
                    size_bucket = ?,
                    headquarters_location = ?,
                    glassdoor_url = ?,
                    notes = ?,
                    is_active = ?,
                    custom_scrape_config = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                company.name,
                company.website,
                company.careers_url,
                company.ats_platform,
                company.ats_slug,
                company.industry,
                company.size_bucket,
                company.headquarters_location,
                company.glassdoor_url,
                company.notes,
                1 if company.is_active else 0,
                json.dumps(company.custom_scrape_config) if company.custom_scrape_config else None,
                company.id,
            ))
        else:
            # Insert new
            cursor.execute("""
                INSERT INTO companies (
                    name, website, careers_url, ats_platform, ats_slug,
                    industry, size_bucket, headquarters_location, glassdoor_url,
                    notes, is_active, custom_scrape_config
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                company.name,
                company.website,
                company.careers_url,
                company.ats_platform,
                company.ats_slug,
                company.industry,
                company.size_bucket,
                company.headquarters_location,
                company.glassdoor_url,
                company.notes,
                1 if company.is_active else 0,
                json.dumps(company.custom_scrape_config) if company.custom_scrape_config else None,
            ))
            company.id = cursor.lastrowid
    
    return company


def get_company_by_id(company_id: int) -> Optional[Company]:
    """Get a company by ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM companies WHERE id = ?", (company_id,))
        row = cursor.fetchone()
        return Company.from_row(row) if row else None


def get_company_by_name(name: str) -> Optional[Company]:
    """Get a company by name."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM companies WHERE name = ?", (name,))
        row = cursor.fetchone()
        return Company.from_row(row) if row else None


def get_company_by_slug(ats_platform: str, ats_slug: str) -> Optional[Company]:
    """Get a company by ATS platform and slug."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM companies WHERE ats_platform = ? AND ats_slug = ?",
            (ats_platform, ats_slug)
        )
        row = cursor.fetchone()
        return Company.from_row(row) if row else None


def get_active_companies(ats_platform: Optional[str] = None) -> list[Company]:
    """
    Get all active companies, optionally filtered by ATS platform.
    
    Args:
        ats_platform: Optional filter by 'greenhouse' or 'lever'.
    
    Returns:
        List of active Company objects.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        if ats_platform:
            cursor.execute(
                "SELECT * FROM companies WHERE is_active = 1 AND ats_platform = ? ORDER BY name",
                (ats_platform,)
            )
        else:
            cursor.execute("SELECT * FROM companies WHERE is_active = 1 ORDER BY name")
        
        return [Company.from_row(row) for row in cursor.fetchall()]


def get_all_companies() -> list[Company]:
    """Get all companies."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM companies ORDER BY name")
        return [Company.from_row(row) for row in cursor.fetchall()]


def update_last_scraped(company_id: int) -> None:
    """Update the last_scraped_at timestamp for a company."""
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE companies SET last_scraped_at = CURRENT_TIMESTAMP WHERE id = ?",
            (company_id,)
        )


def delete_company(company_id: int) -> bool:
    """
    Delete a company by ID.
    
    Returns:
        True if deleted, False if not found.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM companies WHERE id = ?", (company_id,))
        return cursor.rowcount > 0


def count_companies(active_only: bool = False) -> int:
    """Count total companies."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if active_only:
            cursor.execute("SELECT COUNT(*) FROM companies WHERE is_active = 1")
        else:
            cursor.execute("SELECT COUNT(*) FROM companies")
        return cursor.fetchone()[0]
