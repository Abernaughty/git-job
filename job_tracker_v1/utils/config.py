from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file, returning an empty dict if it's blank."""
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_settings(path: Path) -> dict[str, Any]:
    return load_yaml(path)


def load_searches(path: Path) -> list[dict[str, Any]]:
    data = load_yaml(path)
    return list(data.get("searches", []))
