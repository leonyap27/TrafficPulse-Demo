"""Tests for scripts/release_docs/visuals.py.

Each builder is a pure function over already-categorized data. Tests assert
the rendered markdown contains the expected structural elements without
snapshot-matching the entire string (template tweaks shouldn't flake tests).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from release_docs.models import BundleTicket, CategorizedBucket  # noqa: E402
from release_docs.visuals import (  # noqa: E402
    build_business_mindmap,
    build_business_pie,
    build_components_mermaid,
)


def _bucket(name, n_tickets):
    tickets = [
        BundleTicket(key=f"FP-{100 + i}", work_type="sprint", summary=f"ticket {i}")
        for i in range(n_tickets)
    ]
    return CategorizedBucket(bucket=name, tickets=tickets)


_SAMPLE_BUCKETS = [_bucket("Infra", 8), _bucket("Other", 7)]


def test_components_mermaid_starts_with_fence_and_flowchart():
    output = build_components_mermaid("0.4.6", _SAMPLE_BUCKETS)
    assert output.startswith("```mermaid\nflowchart LR")
    assert output.endswith("```")


def test_components_mermaid_includes_release_version_root():
    output = build_components_mermaid("0.4.6", _SAMPLE_BUCKETS)
    assert "R([Release v0.4.6])" in output


def test_components_mermaid_includes_each_bucket_with_count():
    output = build_components_mermaid("0.4.6", _SAMPLE_BUCKETS)
    assert "Infra<br/>8 changes" in output
    assert "Other<br/>7 changes" in output


def test_components_mermaid_singular_change_label():
    buckets = [_bucket("Frontend", 1)]
    output = build_components_mermaid("0.4.7", buckets)
    assert "Frontend<br/>1 change" in output
    assert "1 changes" not in output


def test_components_mermaid_empty_buckets_returns_empty():
    assert build_components_mermaid("0.4.6", []) == ""


def test_business_pie_starts_with_fence():
    output = build_business_pie(_SAMPLE_BUCKETS)
    assert output.startswith("```mermaid\npie title What shipped")
    assert output.endswith("```")


def test_business_pie_includes_each_bucket_with_count():
    output = build_business_pie(_SAMPLE_BUCKETS)
    assert '"Infra" : 8' in output
    assert '"Other" : 7' in output


def test_business_pie_empty_buckets_returns_empty():
    assert build_business_pie([]) == ""


def test_business_mindmap_includes_root_version():
    output = build_business_mindmap("0.4.6", _SAMPLE_BUCKETS)
    assert "root((v0.4.6))" in output


def test_business_mindmap_includes_bucket_emoji_and_count():
    output = build_business_mindmap("0.4.6", _SAMPLE_BUCKETS)
    assert "🏗️ Infra (8)" in output
    assert "📦 Other (7)" in output


def test_business_mindmap_unknown_bucket_falls_back_to_default_emoji():
    # Even though every Bucket has an entry, defend against future Bucket
    # types being added without updating _BUCKET_EMOJI.
    buckets = [_bucket("Security", 2)]
    output = build_business_mindmap("0.4.6", buckets)
    assert "🔒 Security (2)" in output


def test_business_mindmap_empty_buckets_returns_empty():
    assert build_business_mindmap("0.4.6", []) == ""
