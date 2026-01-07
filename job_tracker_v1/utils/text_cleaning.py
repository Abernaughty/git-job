from __future__ import annotations

import re


_whitespace_re = re.compile(r"\s+")


def normalize_whitespace(text: str) -> str:
    return _whitespace_re.sub(" ", text).strip()
