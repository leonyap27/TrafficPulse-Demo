"""Tests for scripts/release_docs/categorizer.py."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from release_docs.categorizer import categorize_bundle, categorize_ticket  # noqa: E402
from release_docs.models import BundleTicket  # noqa: E402


def _ticket(
    key: str,
    *,
    summary: str = "stub",
    work_type: str = "sprint",
    components: list[str] | None = None,
    labels: list[str] | None = None,
    parent_epic_key: str | None = None,
) -> BundleTicket:
    return BundleTicket(
        key=key,
        work_type=work_type,  # type: ignore[arg-type]
        summary=summary,
        components=components or [],
        labels=labels or [],
        parent_epic_key=parent_epic_key,
    )


def test_component_match_takes_precedence():
    ticket = _ticket(
        "FP-1",
        components=["frontend"],
        labels=["security"],
        parent_epic_key="FP-89",
    )
    assert categorize_ticket(ticket) == "Frontend"


def test_label_fallback_when_no_component():
    ticket = _ticket("FP-2", labels=["security"], parent_epic_key="FP-89")
    assert categorize_ticket(ticket) == "Security"


def test_parent_epic_fallback_when_no_component_or_label():
    ticket = _ticket("FP-3", parent_epic_key="FP-89")
    assert categorize_ticket(ticket) == "Infra"


def test_parent_epic_mapping_covers_release_governance_and_dev_env():
    # FP-183 = release governance children; FP-162 = DEV-env setup children.
    assert categorize_ticket(_ticket("FP-1", parent_epic_key="FP-183")) == "Infra"
    assert categorize_ticket(_ticket("FP-2", parent_epic_key="FP-162")) == "Infra"


def test_other_when_nothing_matches():
    ticket = _ticket("FP-4")
    assert categorize_ticket(ticket) == "Other"


def test_component_match_is_case_insensitive():
    assert categorize_ticket(_ticket("FP-5", components=["FRONTEND"])) == "Frontend"
    assert categorize_ticket(_ticket("FP-6", components=["Backend"])) == "Backend"


def test_agents_rag_bucket_from_components():
    assert categorize_ticket(_ticket("FP-7", components=["rag"])) == "Agents+RAG"
    assert categorize_ticket(_ticket("FP-8", components=["knowledge-base"])) == "Agents+RAG"


def test_categorize_bundle_returns_buckets_in_canonical_order():
    tickets = [
        _ticket("FP-INFRA", components=["infra"]),
        _ticket("FP-FRONT", components=["frontend"]),
        _ticket("FP-BACK", components=["backend"]),
    ]
    result = categorize_bundle(tickets)
    bucket_names = [b.bucket for b in result]
    assert bucket_names == ["Frontend", "Backend", "Infra"]


def test_categorize_bundle_drops_empty_buckets():
    tickets = [_ticket("FP-1", components=["frontend"])]
    result = categorize_bundle(tickets)
    assert len(result) == 1
    assert result[0].bucket == "Frontend"


def test_categorize_bundle_preserves_within_bucket_order():
    tickets = [
        _ticket("FP-A", components=["frontend"], summary="a"),
        _ticket("FP-B", components=["frontend"], summary="b"),
        _ticket("FP-C", components=["frontend"], summary="c"),
    ]
    result = categorize_bundle(tickets)
    assert [t.key for t in result[0].tickets] == ["FP-A", "FP-B", "FP-C"]


def test_unmatched_tickets_land_in_other_bucket():
    tickets = [
        _ticket("FP-OK", components=["frontend"]),
        _ticket("FP-NOPE"),
    ]
    result = categorize_bundle(tickets)
    bucket_names = [b.bucket for b in result]
    assert "Other" in bucket_names
    other = next(b for b in result if b.bucket == "Other")
    assert [t.key for t in other.tickets] == ["FP-NOPE"]
