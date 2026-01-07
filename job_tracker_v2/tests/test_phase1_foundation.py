"""
Phase 1 Foundation Tests - Database and Models

Run with: pytest tests/test_phase1_foundation.py -v
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest


class TestDatabaseSchema:
    """Test database schema creation and structure."""
    
    def test_database_initialization(self, test_db):
        """Test that database initializes correctly."""
        from database.connection import get_db_connection
        
        with get_db_connection(test_db) as conn:
            cursor = conn.cursor()
            
            # Check that tables exist
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
            """)
            tables = [row[0] for row in cursor.fetchall()]
            
            expected_tables = [
                'application_events',
                'companies',
                'llm_usage',
                'my_preferences',
                'my_skills',
                'posting_skills',
                'postings',
                'scrape_log',
                'skills',
                'target_roles',
                'weekly_snapshots',
            ]
            
            for table in expected_tables:
                assert table in tables, f"Missing table: {table}"
    
    def test_companies_table_structure(self, test_db):
        """Test companies table has expected columns."""
        from database.connection import get_db_connection
        
        with get_db_connection(test_db) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(companies)")
            columns = {row[1] for row in cursor.fetchall()}
            
            expected_columns = {
                'id', 'name', 'website', 'careers_url', 'ats_platform', 
                'ats_slug', 'industry', 'size_bucket', 'headquarters_location',
                'glassdoor_url', 'notes', 'is_active', 'custom_scrape_config',
                'created_at', 'updated_at', 'last_scraped_at'
            }
            
            for col in expected_columns:
                assert col in columns, f"Missing column: {col}"
    
    def test_postings_table_structure(self, test_db):
        """Test postings table has expected columns."""
        from database.connection import get_db_connection
        
        with get_db_connection(test_db) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(postings)")
            columns = {row[1] for row in cursor.fetchall()}
            
            # Check key columns
            key_columns = {
                'id', 'company_id', 'source_url', 'source_site', 
                'raw_title', 'raw_description', 'normalized_title',
                'salary_min', 'salary_max', 'match_score', 'status'
            }
            
            for col in key_columns:
                assert col in columns, f"Missing column: {col}"
    
    def test_foreign_key_enabled(self, test_db):
        """Test that foreign keys are enabled."""
        from database.connection import get_db_connection
        
        with get_db_connection(test_db) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys")
            result = cursor.fetchone()[0]
            assert result == 1, "Foreign keys should be enabled"
    
    def test_unique_constraint_source_url(self, test_db):
        """Test that source_url has unique constraint."""
        from database.connection import get_db_connection
        import sqlite3
        
        with get_db_connection(test_db) as conn:
            cursor = conn.cursor()
            
            # Insert a posting
            cursor.execute("""
                INSERT INTO postings (source_url, source_site, raw_title)
                VALUES ('https://example.com/job/1', 'greenhouse', 'Test Job')
            """)
            
            # Try to insert duplicate - should fail
            with pytest.raises(sqlite3.IntegrityError):
                cursor.execute("""
                    INSERT INTO postings (source_url, source_site, raw_title)
                    VALUES ('https://example.com/job/1', 'greenhouse', 'Duplicate Job')
                """)


class TestCompanyModel:
    """Test Company model and database operations."""
    
    def test_create_company(self, test_db):
        """Test creating a company."""
        from models.company import Company, save_company, get_company_by_id
        from config.settings import settings
        
        # Temporarily override database path
        original_path = settings.database_path
        settings.database_path = test_db
        
        try:
            company = Company(
                name="Test Company",
                website="https://test.com",
                ats_platform="greenhouse",
                ats_slug="testcompany",
                industry="tech",
                size_bucket="medium",
            )
            
            saved = save_company(company)
            assert saved.id is not None
            
            # Retrieve and verify
            retrieved = get_company_by_id(saved.id)
            assert retrieved is not None
            assert retrieved.name == "Test Company"
            assert retrieved.ats_platform == "greenhouse"
            assert retrieved.ats_slug == "testcompany"
        finally:
            settings.database_path = original_path
    
    def test_company_from_dict(self):
        """Test creating company from dictionary."""
        from models.company import Company
        
        data = {
            'name': 'Dict Company',
            'website': 'https://dict.com',
            'ats_platform': 'lever',
            'ats_slug': 'dictco',
            'extra_field': 'should be ignored',
        }
        
        company = Company.from_dict(data)
        assert company.name == 'Dict Company'
        assert company.ats_platform == 'lever'
        assert not hasattr(company, 'extra_field')
    
    def test_company_greenhouse_url(self):
        """Test Greenhouse URL generation."""
        from models.company import Company
        
        company = Company(
            name="GH Company",
            ats_platform="greenhouse",
            ats_slug="ghcompany",
        )
        
        assert company.greenhouse_url == "https://boards.greenhouse.io/ghcompany"
        assert company.greenhouse_api_url == "https://boards-api.greenhouse.io/v1/boards/ghcompany/jobs"
    
    def test_company_lever_url(self):
        """Test Lever URL generation."""
        from models.company import Company
        
        company = Company(
            name="Lever Company",
            ats_platform="lever",
            ats_slug="leverco",
        )
        
        assert company.lever_url == "https://jobs.lever.co/leverco"
        assert company.greenhouse_url is None
    
    def test_get_active_companies(self, test_db):
        """Test getting active companies."""
        from models.company import Company, save_company, get_active_companies
        from config.settings import settings
        
        original_path = settings.database_path
        settings.database_path = test_db
        
        try:
            # Create active and inactive companies
            active = Company(name="Active Co", ats_platform="greenhouse", ats_slug="active", is_active=True)
            inactive = Company(name="Inactive Co", ats_platform="greenhouse", ats_slug="inactive", is_active=False)
            
            save_company(active)
            save_company(inactive)
            
            # Get active companies
            companies = get_active_companies()
            names = [c.name for c in companies]
            
            assert "Active Co" in names
            assert "Inactive Co" not in names
        finally:
            settings.database_path = original_path


class TestSkillModel:
    """Test Skill model and normalization."""
    
    def test_skill_normalization_python(self):
        """Test Python skill aliases normalize correctly."""
        from models.skill import normalize_skill_name
        
        assert normalize_skill_name("python") == "Python"
        assert normalize_skill_name("Python3") == "Python"
        assert normalize_skill_name("py") == "Python"
        assert normalize_skill_name("PYTHON") == "Python"
    
    def test_skill_normalization_kubernetes(self):
        """Test Kubernetes aliases normalize correctly."""
        from models.skill import normalize_skill_name
        
        assert normalize_skill_name("kubernetes") == "Kubernetes"
        assert normalize_skill_name("k8s") == "Kubernetes"
        assert normalize_skill_name("kube") == "Kubernetes"
    
    def test_skill_normalization_aws(self):
        """Test AWS aliases normalize correctly."""
        from models.skill import normalize_skill_name
        
        assert normalize_skill_name("aws") == "Amazon Web Services"
        assert normalize_skill_name("Amazon AWS") == "Amazon Web Services"
    
    def test_skill_normalization_unknown(self):
        """Test unknown skills get title case."""
        from models.skill import normalize_skill_name
        
        assert normalize_skill_name("some unknown skill") == "Some Unknown Skill"
        assert normalize_skill_name("RUST") == "Rust"
    
    def test_get_or_create_skill(self, test_db):
        """Test get_or_create_skill function."""
        from models.skill import get_or_create_skill, get_skill_by_name
        from config.settings import settings
        
        original_path = settings.database_path
        settings.database_path = test_db
        
        try:
            # First call creates
            skill1 = get_or_create_skill("python", category="language")
            assert skill1.id is not None
            assert skill1.name == "Python"
            
            # Second call retrieves
            skill2 = get_or_create_skill("py")  # alias for python
            assert skill2.id == skill1.id
        finally:
            settings.database_path = original_path


class TestPostingModel:
    """Test Posting model and database operations."""
    
    def test_create_posting(self, test_db):
        """Test creating a posting."""
        from models.posting import Posting, save_posting, get_posting_by_id
        from models.company import Company, save_company
        from config.settings import settings
        
        original_path = settings.database_path
        settings.database_path = test_db
        
        try:
            # Create a company first
            company = Company(name="Test Co", ats_platform="greenhouse", ats_slug="testco")
            company = save_company(company)
            
            # Create posting
            posting = Posting(
                company_id=company.id,
                source_url="https://boards.greenhouse.io/testco/jobs/123",
                source_site="greenhouse",
                external_id="123",
                raw_title="Software Engineer",
                raw_description="We are looking for...",
            )
            
            saved = save_posting(posting)
            assert saved.id is not None
            
            # Retrieve and verify
            retrieved = get_posting_by_id(saved.id)
            assert retrieved is not None
            assert retrieved.raw_title == "Software Engineer"
            assert retrieved.status == "new"
        finally:
            settings.database_path = original_path
    
    def test_posting_exists(self, test_db):
        """Test posting_exists function."""
        from models.posting import Posting, save_posting, posting_exists
        from config.settings import settings
        
        original_path = settings.database_path
        settings.database_path = test_db
        
        try:
            url = "https://example.com/job/unique123"
            
            # Should not exist yet
            assert posting_exists(url) is False
            
            # Create posting
            posting = Posting(source_url=url, source_site="greenhouse", raw_title="Test")
            save_posting(posting)
            
            # Now should exist
            assert posting_exists(url) is True
        finally:
            settings.database_path = original_path
    
    def test_salary_range_display(self):
        """Test salary range formatting."""
        from models.posting import Posting
        
        # Both min and max
        p1 = Posting(salary_min=100000, salary_max=150000)
        assert p1.salary_range_display == "$100,000 - $150,000"
        
        # Only min
        p2 = Posting(salary_min=120000)
        assert p2.salary_range_display == "$120,000+"
        
        # Only max
        p3 = Posting(salary_max=180000)
        assert p3.salary_range_display == "Up to $180,000"
        
        # Neither
        p4 = Posting()
        assert p4.salary_range_display == "Not specified"


class TestDatabaseHealth:
    """Test database health check functionality."""
    
    def test_check_database_health(self, test_db):
        """Test database health check."""
        from database.connection import check_database_health
        
        stats = check_database_health(test_db)
        
        assert stats['exists'] is True
        assert 'tables' in stats
        assert 'companies' in stats['tables']
        assert 'postings' in stats['tables']
        assert 'size_bytes' in stats
    
    def test_health_check_nonexistent_db(self, test_db_path):
        """Test health check on non-existent database."""
        from database.connection import check_database_health
        
        # Delete the temp file (it was created but not initialized)
        if test_db_path.exists():
            test_db_path.unlink()
        
        stats = check_database_health(test_db_path)
        assert stats['exists'] is False


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
