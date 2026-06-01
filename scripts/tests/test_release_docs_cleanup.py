"""Tests for scripts/release_docs/cleanup.py."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from release_docs.cleanup import clean_summary  # noqa: E402


def test_strips_fp_key_prefix():
    assert clean_summary("FP-185 Design Jira Dev-to-UAT change tracker") == (
        "Design Jira Dev-to-UAT change tracker"
    )


def test_strips_fp_key_prefix_with_dash_separator():
    assert clean_summary("FP-185 — Design Jira tracker") == "Design Jira tracker"
    assert clean_summary("FP-185 - Design Jira tracker") == "Design Jira tracker"
    assert clean_summary("FP-185: Design Jira tracker") == "Design Jira tracker"


def test_strips_inline_work_type_tag():
    assert clean_summary("[sprint] Design tracker") == "Design tracker"
    assert clean_summary("[tech-debt] Lockdown UAT") == "Lockdown UAT"
    assert clean_summary("[carry-over] Old POC story") == "Old POC story"


def test_strips_both_prefix_and_tag():
    assert clean_summary("FP-185 [sprint] Design tracker") == "Design tracker"


def test_trims_trailing_punctuation():
    assert clean_summary("Design tracker.") == "Design tracker"
    assert clean_summary("Design tracker;") == "Design tracker"
    assert clean_summary("Design tracker.;,  ") == "Design tracker"


def test_collapses_internal_whitespace():
    assert clean_summary("Design   tracker   pilot") == "Design tracker pilot"


def test_empty_input_returns_empty():
    assert clean_summary("") == ""


def test_does_not_strip_fp_substring_in_body():
    # The prefix-strip is anchored to start-of-string only.
    assert clean_summary("Reference FP-123 in this work") == "Reference FP-123 in this work"
