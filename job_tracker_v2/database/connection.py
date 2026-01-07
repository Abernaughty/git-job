"""
Database connection management for SQLite.
Provides connection handling, schema initialization, and context managers.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional

import structlog

from config.settings import settings, PROJECT_ROOT

logger = structlog.get_logger()

# Path to schema file
SCHEMA_PATH = PROJECT_ROOT / "database" / "schema.sql"


def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """
    Create a new database connection.
    
    Args:
        db_path: Optional path to database file. Uses settings default if not provided.
    
    Returns:
        SQLite connection with row factory enabled.
    """
    path = db_path or settings.database_path
    
    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row  # Enable dict-like access to rows
    
    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON")
    
    # Enable WAL mode for better concurrent access
    conn.execute("PRAGMA journal_mode = WAL")
    
    return conn


@contextmanager
def get_db_connection(db_path: Optional[Path] = None) -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager for database connections.
    Automatically commits on success, rolls back on error.
    
    Usage:
        with get_db_connection() as conn:
            conn.execute("INSERT INTO ...")
    """
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error("Database error, rolling back", error=str(e))
        raise
    finally:
        conn.close()


@contextmanager
def get_db_cursor(db_path: Optional[Path] = None) -> Generator[sqlite3.Cursor, None, None]:
    """
    Context manager for database cursor.
    
    Usage:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT * FROM companies")
            rows = cursor.fetchall()
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        yield cursor


def init_database(db_path: Optional[Path] = None) -> None:
    """
    Initialize the database with the schema.
    Safe to call multiple times (uses IF NOT EXISTS).
    
    Args:
        db_path: Optional path to database file.
    """
    path = db_path or settings.database_path
    logger.info("Initializing database", path=str(path))
    
    # Read schema file
    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(f"Schema file not found: {SCHEMA_PATH}")
    
    schema_sql = SCHEMA_PATH.read_text()
    
    with get_db_connection(path) as conn:
        conn.executescript(schema_sql)
    
    logger.info("Database initialized successfully", path=str(path))


def reset_database(db_path: Optional[Path] = None) -> None:
    """
    Drop all tables and reinitialize the database.
    WARNING: This deletes all data!
    
    Args:
        db_path: Optional path to database file.
    """
    path = db_path or settings.database_path
    logger.warning("Resetting database - all data will be lost!", path=str(path))
    
    # Get list of tables
    with get_db_connection(path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = [row[0] for row in cursor.fetchall()]
        
        # Disable foreign keys temporarily
        conn.execute("PRAGMA foreign_keys = OFF")
        
        # Drop all tables
        for table in tables:
            conn.execute(f"DROP TABLE IF EXISTS {table}")
            logger.info("Dropped table", table=table)
        
        # Re-enable foreign keys
        conn.execute("PRAGMA foreign_keys = ON")
    
    # Reinitialize
    init_database(path)
    logger.info("Database reset complete")


def check_database_health(db_path: Optional[Path] = None) -> dict:
    """
    Check database health and return statistics.
    
    Returns:
        Dictionary with table counts and database info.
    """
    path = db_path or settings.database_path
    
    if not path.exists():
        return {"exists": False, "error": "Database file does not exist"}
    
    stats = {"exists": True, "path": str(path), "tables": {}}
    
    try:
        with get_db_connection(path) as conn:
            cursor = conn.cursor()
            
            # Get table names
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            tables = [row[0] for row in cursor.fetchall()]
            
            # Count rows in each table
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                stats["tables"][table] = count
            
            # Get database size
            cursor.execute("PRAGMA page_count")
            page_count = cursor.fetchone()[0]
            cursor.execute("PRAGMA page_size")
            page_size = cursor.fetchone()[0]
            stats["size_bytes"] = page_count * page_size
            stats["size_mb"] = round(stats["size_bytes"] / (1024 * 1024), 2)
            
    except Exception as e:
        stats["error"] = str(e)
    
    return stats


# Convenience functions for common queries

def row_to_dict(row: sqlite3.Row) -> dict:
    """Convert a sqlite3.Row to a dictionary."""
    return dict(zip(row.keys(), row))


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict]:
    """Convert a list of sqlite3.Row to list of dictionaries."""
    return [row_to_dict(row) for row in rows]


if __name__ == "__main__":
    # Simple CLI for database operations
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "init":
            init_database()
            print("Database initialized.")
        elif command == "reset":
            confirm = input("This will delete all data. Type 'yes' to confirm: ")
            if confirm == "yes":
                reset_database()
                print("Database reset complete.")
            else:
                print("Cancelled.")
        elif command == "health":
            stats = check_database_health()
            import json
            print(json.dumps(stats, indent=2))
        else:
            print(f"Unknown command: {command}")
            print("Available commands: init, reset, health")
    else:
        print("Usage: python -m database.connection <command>")
        print("Commands: init, reset, health")
