from __future__ import annotations


def is_duplicate(existing_signature: str, new_signature: str) -> bool:
    """Determine whether two job signatures represent the same listing."""
    return existing_signature == new_signature
