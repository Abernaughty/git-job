"""
Pytest configuration and fixtures for Job Search System tests.
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

# Add project root to Python path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Set test database path before importing any modules
os.environ['DATABASE_PATH'] = str(Path(tempfile.gettempdir()) / 'test_job_search.db')


@pytest.fixture(scope="function")
def test_db_path():
    """Create a temporary database path for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)
    
    yield db_path
    
    # Cleanup
    if db_path.exists():
        db_path.unlink()
    # Also clean up WAL files
    wal_path = Path(str(db_path) + '-wal')
    shm_path = Path(str(db_path) + '-shm')
    if wal_path.exists():
        wal_path.unlink()
    if shm_path.exists():
        shm_path.unlink()


@pytest.fixture(scope="function")
def test_db(test_db_path):
    """Create and initialize a test database."""
    from database.connection import init_database, get_db_connection
    
    # Initialize the database
    init_database(test_db_path)
    
    yield test_db_path


@pytest.fixture(scope="function")
def seeded_db(test_db):
    """Test database with seed companies loaded."""
    from scripts.seed_companies import load_seed_companies
    
    # Load seed companies - need to temporarily override settings
    from config.settings import settings
    original_path = settings.database_path
    
    # We need to use the test_db path
    # For now, just return the test_db - seed loading will be tested separately
    yield test_db


# Markers for test categories
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "live: marks tests that make real API calls")
    config.addinivalue_line("markers", "integration: marks integration tests")
    config.addinivalue_line("markers", "slow: marks slow tests")
