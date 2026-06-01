"""Deterministic title cleanup applied before categorization and rendering."""

from __future__ import annotations

import re

_FP_PREFIX_RE = re.compile(r"^FP-\d+\s*[—\-:]?\s*", re.IGNORECASE)
_WORK_TYPE_TAG_RE = re.compile(r"\[(sprint|tech-debt|carry-over)\]\s*", re.IGNORECASE)
_TRAILING_PUNCT_RE = re.compile(r"[.;,\s]+$")
_WHITESPACE_RE = re.compile(r"\s+")


def clean_summary(raw: str) -> str:
    """Normalize a raw bundle line into a renderable summary.

    Strips the ``FP-XXX `` key prefix (the key is shown separately in the
    output), strips inline work-type tags like ``[sprint]`` (also shown
    separately), collapses internal whitespace, and trims trailing
    punctuation. Returns an empty string if the input collapses to nothing.

    Args:
        raw: Raw summary text from the tracker bundle line.

    Returns:
        Cleaned summary, suitable for rendering as a bullet.
    """
    if not raw:
        return ""
    text = _FP_PREFIX_RE.sub("", raw)
    text = _WORK_TYPE_TAG_RE.sub("", text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    text = _TRAILING_PUNCT_RE.sub("", text)
    return text
