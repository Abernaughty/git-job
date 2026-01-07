from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import sqlite3
from typing import Any, Optional


@dataclass
class Job:
    id: int
    external_id: str
    source: str
    url: str
    title: str
    company: str
    location: Optional[str]
    salary_raw: Optional[str]
    description_raw: str
    job_type: Optional[str]
    date_posted: Optional[str]
    first_seen_at: Optional[str]
    last_seen_at: Optional[str]
    is_active: int


def _utc_now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def _row_to_job(row: sqlite3.Row) -> Job:
    return Job(
        id=row["id"],
        external_id=row["external_id"],
        source=row["source"],
        url=row["url"],
        title=row["title"],
        company=row["company"],
        location=row["location"],
        salary_raw=row["salary_raw"],
        description_raw=row["description_raw"],
        job_type=row["job_type"],
        date_posted=row["date_posted"],
        first_seen_at=row["first_seen_at"],
        last_seen_at=row["last_seen_at"],
        is_active=row["is_active"],
    )


def get_job(conn: sqlite3.Connection, job_id: int) -> Optional[Job]:
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM jobs WHERE id = ?",
        (job_id,),
    ).fetchone()
    if row is None:
        return None
    return _row_to_job(row)


def list_jobs(
    conn: sqlite3.Connection,
    limit: int = 50,
    since_iso: Optional[str] = None,
) -> list[Job]:
    conn.row_factory = sqlite3.Row
    params: list[Any] = []
    where_clause = ""
    if since_iso:
        where_clause = "WHERE last_seen_at >= ?"
        params.append(since_iso)
    params.append(limit)
    rows = conn.execute(
        f"SELECT * FROM jobs {where_clause} ORDER BY last_seen_at DESC LIMIT ?",
        params,
    ).fetchall()
    return [_row_to_job(row) for row in rows]


def upsert_job(conn: sqlite3.Connection, job_data: dict[str, Any]) -> int:
    """Insert or update a job record and return its id."""
    now = _utc_now()
    existing = conn.execute(
        "SELECT id, first_seen_at FROM jobs WHERE source = ? AND external_id = ?",
        (job_data["source"], job_data["external_id"]),
    ).fetchone()

    if existing:
        job_id = existing[0]
        conn.execute(
            """
            UPDATE jobs
            SET url = ?,
                title = ?,
                company = ?,
                location = ?,
                salary_raw = ?,
                description_raw = ?,
                job_type = ?,
                date_posted = ?,
                last_seen_at = ?,
                updated_at = ?,
                is_active = 1
            WHERE id = ?
            """,
            (
                job_data.get("url"),
                job_data.get("title"),
                job_data.get("company"),
                job_data.get("location"),
                job_data.get("salary_raw"),
                job_data.get("description_raw"),
                job_data.get("job_type"),
                job_data.get("date_posted"),
                now,
                now,
                job_id,
            ),
        )
        conn.commit()
        return job_id

    skills_json = json.dumps(job_data.get("skills")) if job_data.get("skills") else None
    qualifications_json = (
        json.dumps(job_data.get("qualifications"))
        if job_data.get("qualifications")
        else None
    )
    cursor = conn.execute(
        """
        INSERT INTO jobs (
            external_id,
            source,
            url,
            title,
            company,
            location,
            salary_raw,
            description_raw,
            job_type,
            date_posted,
            skills,
            qualifications,
            first_seen_at,
            last_seen_at,
            created_at,
            updated_at,
            is_active
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """,
        (
            job_data.get("external_id"),
            job_data.get("source"),
            job_data.get("url"),
            job_data.get("title"),
            job_data.get("company"),
            job_data.get("location"),
            job_data.get("salary_raw"),
            job_data.get("description_raw"),
            job_data.get("job_type"),
            job_data.get("date_posted"),
            skills_json,
            qualifications_json,
            now,
            now,
            now,
            now,
        ),
    )
    conn.commit()
    if cursor.lastrowid is None:
        raise RuntimeError("Failed to insert job row")
    return int(cursor.lastrowid)
