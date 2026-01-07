from __future__ import annotations

import sqlite3
from pathlib import Path


def connect(db_path: str) -> sqlite3.Connection:
    """Create a SQLite connection with foreign keys enabled."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize_db(db_path: str) -> sqlite3.Connection:
    """Connect to the database and ensure schema exists."""
    conn = connect(db_path)
    initialize_schema(conn)
    return conn


def initialize_schema(conn: sqlite3.Connection) -> None:
    """Create tables if they do not exist."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY,
            external_id TEXT NOT NULL,
            source TEXT NOT NULL,
            url TEXT NOT NULL,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            location TEXT,
            salary_raw TEXT,
            salary_min INTEGER,
            salary_max INTEGER,
            description_raw TEXT NOT NULL,
            experience_years_min INTEGER,
            experience_years_max INTEGER,
            skills TEXT,
            qualifications TEXT,
            job_type TEXT,
            remote_status TEXT,
            date_posted TEXT,
            first_seen_at TEXT,
            last_seen_at TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT,
            updated_at TEXT,
            UNIQUE (source, external_id)
        );

        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY,
            job_id INTEGER,
            status TEXT NOT NULL,
            company TEXT,
            title TEXT,
            url TEXT,
            applied_at TEXT,
            salary_offered INTEGER,
            notes TEXT,
            contacts TEXT,
            next_action TEXT,
            next_action_date TEXT,
            created_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (job_id) REFERENCES jobs(id)
        );

        CREATE TABLE IF NOT EXISTS application_events (
            id INTEGER PRIMARY KEY,
            application_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            event_date TEXT NOT NULL,
            notes TEXT,
            created_at TEXT,
            FOREIGN KEY (application_id) REFERENCES applications(id)
        );
        """
    )
