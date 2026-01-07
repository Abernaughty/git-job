"""
Job Posting model and database operations.
"""

from dataclasses import dataclass
from datetime import datetime, date
from typing import Optional
import json

from database.connection import get_db_connection, row_to_dict


@dataclass
class Posting:
    """Represents a job posting."""
    
    id: Optional[int] = None
    company_id: Optional[int] = None
    role_id: Optional[int] = None
    
    # Source tracking
    source_url: str = ""
    source_site: str = ""  # greenhouse, lever, company_direct
    external_id: Optional[str] = None
    
    # Raw data
    raw_title: str = ""
    raw_description: Optional[str] = None
    raw_html: Optional[str] = None
    posted_date: Optional[date] = None
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    
    # LLM-extracted data
    normalized_title: Optional[str] = None
    seniority_level: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_type: Optional[str] = None
    salary_currency: str = "USD"
    experience_years_min: Optional[int] = None
    experience_years_max: Optional[int] = None
    education_requirement: Optional[str] = None
    
    # Location
    location_raw: Optional[str] = None
    location_city: Optional[str] = None
    location_state: Optional[str] = None
    remote_type: Optional[str] = None  # onsite, hybrid, remote_local, remote_us, remote_global
    
    # Clearance
    clearance_required: Optional[str] = None
    clearance_sponsorship: Optional[str] = None
    
    # Metadata
    department: Optional[str] = None
    team: Optional[str] = None
    reports_to: Optional[str] = None
    travel_requirement: Optional[str] = None
    visa_sponsorship: Optional[str] = None
    benefits_summary: Optional[list] = None
    red_flags: Optional[list] = None
    
    # Scoring
    match_score: Optional[float] = None
    skill_match_details: Optional[dict] = None
    
    # Status
    status: str = "new"
    interest_level: Optional[int] = None
    notes: Optional[str] = None
    
    # Application tracking
    applied_at: Optional[datetime] = None
    application_method: Optional[str] = None
    resume_version: Optional[str] = None
    cover_letter_notes: Optional[str] = None
    
    # Processing
    parse_version: Optional[str] = None
    parse_confidence: Optional[float] = None
    needs_reparse: bool = False
    
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @classmethod
    def from_row(cls, row) -> "Posting":
        """Create a Posting from a database row."""
        data = row_to_dict(row) if hasattr(row, 'keys') else dict(row)
        
        # Parse JSON fields
        for json_field in ['benefits_summary', 'red_flags', 'skill_match_details']:
            if data.get(json_field):
                try:
                    data[json_field] = json.loads(data[json_field])
                except (json.JSONDecodeError, TypeError):
                    data[json_field] = None
        
        # Convert needs_reparse to bool
        data['needs_reparse'] = bool(data.get('needs_reparse', 0))
        
        return cls(**data)
    
    @classmethod
    def from_dict(cls, data: dict) -> "Posting":
        """Create a Posting from a dictionary."""
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)
    
    def to_dict(self) -> dict:
        """Convert Posting to a dictionary for database storage."""
        return {
            'company_id': self.company_id,
            'role_id': self.role_id,
            'source_url': self.source_url,
            'source_site': self.source_site,
            'external_id': self.external_id,
            'raw_title': self.raw_title,
            'raw_description': self.raw_description,
            'raw_html': self.raw_html,
            'posted_date': self.posted_date,
            'normalized_title': self.normalized_title,
            'seniority_level': self.seniority_level,
            'salary_min': self.salary_min,
            'salary_max': self.salary_max,
            'salary_type': self.salary_type,
            'salary_currency': self.salary_currency,
            'experience_years_min': self.experience_years_min,
            'experience_years_max': self.experience_years_max,
            'education_requirement': self.education_requirement,
            'location_raw': self.location_raw,
            'location_city': self.location_city,
            'location_state': self.location_state,
            'remote_type': self.remote_type,
            'clearance_required': self.clearance_required,
            'clearance_sponsorship': self.clearance_sponsorship,
            'department': self.department,
            'team': self.team,
            'reports_to': self.reports_to,
            'travel_requirement': self.travel_requirement,
            'visa_sponsorship': self.visa_sponsorship,
            'benefits_summary': json.dumps(self.benefits_summary) if self.benefits_summary else None,
            'red_flags': json.dumps(self.red_flags) if self.red_flags else None,
            'match_score': self.match_score,
            'skill_match_details': json.dumps(self.skill_match_details) if self.skill_match_details else None,
            'status': self.status,
            'interest_level': self.interest_level,
            'notes': self.notes,
            'applied_at': self.applied_at,
            'application_method': self.application_method,
            'resume_version': self.resume_version,
            'cover_letter_notes': self.cover_letter_notes,
            'parse_version': self.parse_version,
            'parse_confidence': self.parse_confidence,
            'needs_reparse': 1 if self.needs_reparse else 0,
        }
    
    @property
    def salary_range_display(self) -> str:
        """Format salary range for display."""
        if not self.salary_min and not self.salary_max:
            return "Not specified"
        if self.salary_min and self.salary_max:
            return f"${self.salary_min:,} - ${self.salary_max:,}"
        if self.salary_min:
            return f"${self.salary_min:,}+"
        return f"Up to ${self.salary_max:,}"


# Database operations

def save_posting(posting: Posting) -> Posting:
    """Insert or update a posting."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        data = posting.to_dict()
        
        if posting.id:
            # Update existing
            set_clause = ", ".join(f"{k} = ?" for k in data.keys())
            values = list(data.values()) + [posting.id]
            cursor.execute(
                f"UPDATE postings SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                values
            )
        else:
            # Insert new
            columns = ", ".join(data.keys())
            placeholders = ", ".join("?" * len(data))
            cursor.execute(
                f"INSERT INTO postings ({columns}) VALUES ({placeholders})",
                list(data.values())
            )
            posting.id = cursor.lastrowid
    
    return posting


def get_posting_by_id(posting_id: int) -> Optional[Posting]:
    """Get a posting by ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM postings WHERE id = ?", (posting_id,))
        row = cursor.fetchone()
        return Posting.from_row(row) if row else None


def get_posting_by_url(source_url: str) -> Optional[Posting]:
    """Get a posting by source URL."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM postings WHERE source_url = ?", (source_url,))
        row = cursor.fetchone()
        return Posting.from_row(row) if row else None


def posting_exists(source_url: str) -> bool:
    """Check if a posting with the given URL already exists."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM postings WHERE source_url = ?", (source_url,))
        return cursor.fetchone() is not None


def update_last_seen(source_url: str) -> None:
    """Update last_seen_at for an existing posting."""
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE postings SET last_seen_at = CURRENT_TIMESTAMP WHERE source_url = ?",
            (source_url,)
        )


def get_postings_needing_extraction() -> list[Posting]:
    """Get postings that have raw data but haven't been extracted yet."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM postings 
            WHERE raw_description IS NOT NULL 
            AND normalized_title IS NULL
            ORDER BY first_seen_at DESC
        """)
        return [Posting.from_row(row) for row in cursor.fetchall()]


def get_postings_needing_scoring() -> list[Posting]:
    """Get postings that have been extracted but not scored."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM postings 
            WHERE normalized_title IS NOT NULL 
            AND match_score IS NULL
            ORDER BY first_seen_at DESC
        """)
        return [Posting.from_row(row) for row in cursor.fetchall()]


def get_postings_by_status(status: str) -> list[Posting]:
    """Get all postings with a given status."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM postings WHERE status = ? ORDER BY first_seen_at DESC",
            (status,)
        )
        return [Posting.from_row(row) for row in cursor.fetchall()]


def get_postings_by_company(company_id: int) -> list[Posting]:
    """Get all postings for a company."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM postings WHERE company_id = ? ORDER BY first_seen_at DESC",
            (company_id,)
        )
        return [Posting.from_row(row) for row in cursor.fetchall()]


def get_top_matches(min_score: float = 0.75, limit: int = 20) -> list[Posting]:
    """Get top matching postings above a score threshold."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM postings 
            WHERE match_score >= ? AND status IN ('new', 'reviewing', 'saved')
            ORDER BY match_score DESC
            LIMIT ?
        """, (min_score, limit))
        return [Posting.from_row(row) for row in cursor.fetchall()]


def get_recent_postings(days: int = 7, limit: int = 100) -> list[Posting]:
    """Get postings from the last N days."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM postings 
            WHERE first_seen_at >= datetime('now', ?)
            ORDER BY first_seen_at DESC
            LIMIT ?
        """, (f"-{days} days", limit))
        return [Posting.from_row(row) for row in cursor.fetchall()]


def update_posting_status(posting_id: int, status: str) -> None:
    """Update the status of a posting."""
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE postings SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, posting_id)
        )


def mark_stale_as_closed(days_stale: int = 7) -> int:
    """Mark postings not seen recently as closed."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE postings SET status = 'closed', updated_at = CURRENT_TIMESTAMP
            WHERE last_seen_at < datetime('now', ?)
            AND status IN ('new', 'reviewing', 'saved')
        """, (f"-{days_stale} days",))
        return cursor.rowcount


def delete_old_postings(days_old: int = 90, protected_statuses: list[str] = None) -> int:
    """Delete postings older than N days, except protected statuses."""
    protected = protected_statuses or ['applied', 'phone_screen', 'interview', 'offer']
    placeholders = ','.join('?' * len(protected))
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
            DELETE FROM postings 
            WHERE first_seen_at < datetime('now', ?)
            AND status NOT IN ({placeholders})
        """, (f"-{days_old} days", *protected))
        return cursor.rowcount


def count_postings(status: Optional[str] = None) -> int:
    """Count postings, optionally filtered by status."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if status:
            cursor.execute("SELECT COUNT(*) FROM postings WHERE status = ?", (status,))
        else:
            cursor.execute("SELECT COUNT(*) FROM postings")
        return cursor.fetchone()[0]


def search_postings(
    query: Optional[str] = None,
    company_id: Optional[int] = None,
    min_score: Optional[float] = None,
    status: Optional[str] = None,
    remote_type: Optional[str] = None,
    limit: int = 100,
) -> list[Posting]:
    """Search postings with various filters."""
    conditions = []
    params = []
    
    if query:
        conditions.append("(raw_title LIKE ? OR raw_description LIKE ?)")
        params.extend([f"%{query}%", f"%{query}%"])
    if company_id:
        conditions.append("company_id = ?")
        params.append(company_id)
    if min_score is not None:
        conditions.append("match_score >= ?")
        params.append(min_score)
    if status:
        conditions.append("status = ?")
        params.append(status)
    if remote_type:
        conditions.append("remote_type = ?")
        params.append(remote_type)
    
    where_clause = " AND ".join(conditions) if conditions else "1=1"
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT * FROM postings 
            WHERE {where_clause}
            ORDER BY match_score DESC NULLS LAST, first_seen_at DESC
            LIMIT ?
        """, (*params, limit))
        return [Posting.from_row(row) for row in cursor.fetchall()]
