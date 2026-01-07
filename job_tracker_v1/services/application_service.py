from __future__ import annotations


class ApplicationService:
    """Create and update application records."""

    def create_from_job(self, job_id: int) -> int:
        raise NotImplementedError
