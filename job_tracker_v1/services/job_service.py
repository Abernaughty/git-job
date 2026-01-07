from __future__ import annotations


class JobService:
    """Query and manage job records."""

    def list_recent(self, since: str | None = None) -> list[dict]:
        raise NotImplementedError
