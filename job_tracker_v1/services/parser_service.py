from __future__ import annotations


class ParserService:
    """Extract structured fields from job descriptions."""

    def parse(self, job_id: int) -> None:
        raise NotImplementedError
