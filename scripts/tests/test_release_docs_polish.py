"""Tests for scripts/release_docs/polish.py.

Uses an injected stub ``PolishClient`` so no Vertex/Gemini call happens. The
Vertex client itself is verified by the pilot run in commit 9, not here.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from release_docs.categorizer import categorize_bundle  # noqa: E402
from release_docs.models import (  # noqa: E402
    BundleTicket,
    CategorizedRelease,
    ReleaseInput,
    ReleaseManifest,
)
from release_docs.polish import distill_talking_points, polish  # noqa: E402


def _release(*tickets: BundleTicket) -> CategorizedRelease:
    release_input = ReleaseInput(
        tracker_key="FP-X",
        tracker_url="https://example/browse/FP-X",
        jira_base_url="https://example",
        manifest=ReleaseManifest(
            version="0.0.1",
            target_env="UAT",
            target_env_detail="UAT",
            release_date="2026-01-01",
            approver="N",
        ),
        change_summary=["c"],
        bundle=list(tickets),
    )
    return CategorizedRelease(
        input=release_input,
        buckets=categorize_bundle(release_input.bundle),
    )


class _ReverseClient:
    """Stub that polishes by reversing each line — easy to spot in assertions."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, list[str], str]] = []

    def polish_lines(
        self, *, bucket: str, lines: list[str], audience: str = "technical"
    ) -> list[str]:
        self.calls.append((bucket, list(lines), audience))
        prefix = "[B]" if audience == "business" else ""
        return [prefix + line[::-1] for line in lines]

    def distill_talking_points(
        self, *, lines: list[str], target_count: int = 5
    ) -> list[str]:
        return [f"distilled-{i}" for i in range(min(target_count, len(lines), 3))]


class _DroppingClient:
    """Stub that returns fewer lines than it got — exercises count-mismatch fallback."""

    def polish_lines(
        self, *, bucket: str, lines: list[str], audience: str = "technical"
    ) -> list[str]:
        return lines[:-1] if lines else lines

    def distill_talking_points(
        self, *, lines: list[str], target_count: int = 5
    ) -> list[str]:
        return []


class _RaisingClient:
    """Stub that raises — exercises exception fallback."""

    def polish_lines(
        self, *, bucket: str, lines: list[str], audience: str = "technical"
    ) -> list[str]:
        raise RuntimeError("simulated vertex outage")

    def distill_talking_points(
        self, *, lines: list[str], target_count: int = 5
    ) -> list[str]:
        raise RuntimeError("simulated vertex outage")


def test_polish_disabled_when_no_client():
    release = _release(
        BundleTicket(key="FP-1", work_type="sprint", summary="Original", components=["frontend"]),
    )
    result = polish(release, client=None)
    assert result.buckets[0].tickets[0].summary == "Original"


def test_polish_rewrites_each_bucket_via_injected_client():
    release = _release(
        BundleTicket(key="FP-1", work_type="sprint", summary="abc", components=["frontend"]),
        BundleTicket(key="FP-2", work_type="sprint", summary="defg", components=["backend"]),
    )
    client = _ReverseClient()
    result = polish(release, client=client)
    by_bucket = {b.bucket: b for b in result.buckets}
    assert by_bucket["Frontend"].tickets[0].summary == "cba"
    assert by_bucket["Backend"].tickets[0].summary == "gfed"
    # Each bucket invoked once.
    bucket_names = [call[0] for call in client.calls]
    assert sorted(bucket_names) == ["Backend", "Frontend"]


def test_polish_preserves_ticket_metadata():
    release = _release(
        BundleTicket(
            key="FP-9",
            work_type="tech-debt",
            summary="raw",
            components=["frontend"],
            labels=["security"],
            parent_epic_key="FP-89",
            parent_epic_summary="Deployment & Operation",
        ),
    )
    result = polish(release, client=_ReverseClient())
    polished = result.buckets[0].tickets[0]
    assert polished.key == "FP-9"
    assert polished.work_type == "tech-debt"
    assert polished.labels == ["security"]
    assert polished.parent_epic_key == "FP-89"
    assert polished.parent_epic_summary == "Deployment & Operation"


def test_polish_falls_back_to_raw_on_count_mismatch():
    release = _release(
        BundleTicket(key="FP-1", work_type="sprint", summary="one", components=["frontend"]),
        BundleTicket(key="FP-2", work_type="sprint", summary="two", components=["frontend"]),
    )
    result = polish(release, client=_DroppingClient())
    bullets = [t.summary for t in result.buckets[0].tickets]
    assert bullets == ["one", "two"]  # raw preserved


def test_polish_falls_back_to_raw_on_client_exception():
    release = _release(
        BundleTicket(key="FP-1", work_type="sprint", summary="raw", components=["frontend"]),
    )
    result = polish(release, client=_RaisingClient())
    assert result.buckets[0].tickets[0].summary == "raw"


def test_polish_business_audience_threads_through_to_client():
    release = _release(
        BundleTicket(key="FP-1", work_type="sprint", summary="hello", components=["frontend"]),
    )
    client = _ReverseClient()
    polish(release, client=client, audience="business")
    # Stub records the audience parameter; business prefix should appear.
    assert client.calls[0][2] == "business"


def test_polish_technical_audience_is_default():
    release = _release(
        BundleTicket(key="FP-1", work_type="sprint", summary="hello", components=["frontend"]),
    )
    client = _ReverseClient()
    polish(release, client=client)
    assert client.calls[0][2] == "technical"


def test_distill_talking_points_returns_empty_without_client():
    assert distill_talking_points(["a", "b", "c"], client=None) == []


def test_distill_talking_points_returns_empty_for_empty_input():
    assert distill_talking_points([], client=_ReverseClient()) == []


def test_distill_talking_points_calls_client():
    result = distill_talking_points(["a", "b", "c"], client=_ReverseClient(), target_count=2)
    # _ReverseClient returns min(target_count, len(lines), 3) distilled placeholders.
    assert result == ["distilled-0", "distilled-1"]


def test_distill_talking_points_falls_back_to_empty_on_exception():
    assert distill_talking_points(["a", "b"], client=_RaisingClient()) == []


def test_polish_empty_categorized_release_returns_empty():
    release_input = ReleaseInput(
        tracker_key="FP-X",
        tracker_url="https://example/browse/FP-X",
        jira_base_url="https://example",
        manifest=ReleaseManifest(
            version="0",
            target_env="UAT",
            target_env_detail="UAT",
            release_date="2026-01-01",
            approver="N",
        ),
        change_summary=[],
        bundle=[],
    )
    release = CategorizedRelease(input=release_input, buckets=[])
    result = polish(release, client=_ReverseClient())
    assert result.buckets == []
