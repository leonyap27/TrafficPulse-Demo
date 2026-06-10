"""Tests for scripts/release_docs/business_renderer.py."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from release_docs.business_renderer import render_business  # noqa: E402
from release_docs.categorizer import categorize_bundle  # noqa: E402
from release_docs.models import (  # noqa: E402
    BundleTicket,
    CategorizedRelease,
    ReleaseInput,
    ReleaseManifest,
)

_FROZEN_STAMP = "2026-05-25T14:00:00+08:00"


def _sample_categorized() -> CategorizedRelease:
    release_input = ReleaseInput(
        tracker_key="FP-194",
        tracker_url="https://ltads.atlassian.net/browse/FP-194",
        jira_base_url="https://ltads.atlassian.net",
        manifest=ReleaseManifest(
            version="0.4.6",
            target_env="UAT",
            target_env_detail="UAT (Cloud Run: funding-paper-agent)",
            release_date="2026-05-27",
            approver="Leon Ye",
            sprint="Sprint 1 (12 May - 26 May 2026)",
        ),
        change_summary=[
            "Adds the release tracker pilot.",
            "Bakes in the versioning standard.",
        ],
        bundle=[
            BundleTicket(
                key="FP-185",
                work_type="sprint",
                summary="Established the per-sprint Dev-to-UAT release tracker.",
                parent_epic_key="FP-183",
            ),
            BundleTicket(
                key="FP-156",
                work_type="sprint",
                summary="Improved how funding paper sections are displayed so users see the full output.",
                components=["frontend"],
            ),
        ],
    )
    return CategorizedRelease(
        input=release_input,
        buckets=categorize_bundle(release_input.bundle),
    )


def test_renders_business_header():
    output = render_business(_sample_categorized(), generated_at=_FROZEN_STAMP)
    assert "# Release v0.4.6 — UAT Highlights" in output
    assert "**Release date:** 2026-05-27" in output
    assert "**Target:** UAT" in output
    assert "**Sprint:** Sprint 1 (12 May - 26 May 2026)" in output


def test_business_header_does_not_leak_technical_target_detail():
    output = render_business(_sample_categorized(), generated_at=_FROZEN_STAMP)
    # The full Cloud Run service name lives only on the technical doc.
    assert "Cloud Run: funding-paper-agent" not in output


def test_renders_change_summary():
    output = render_business(_sample_categorized(), generated_at=_FROZEN_STAMP)
    assert "## Summary" in output
    assert "- Adds the release tracker pilot." in output


def test_renders_talking_points_when_provided():
    output = render_business(
        _sample_categorized(),
        talking_points=["Improved release governance.", "Hardened UAT runtime identity."],
        generated_at=_FROZEN_STAMP,
    )
    assert "## Talking points" in output
    assert "- Improved release governance." in output
    assert "- Hardened UAT runtime identity." in output
    # Placeholder should not appear when talking points are present.
    assert "Run with `--polish`" not in output


def test_renders_placeholder_when_no_talking_points():
    output = render_business(_sample_categorized(), generated_at=_FROZEN_STAMP)
    assert "## Talking points" in output
    assert "Run with `--polish`" in output


def test_renders_what_shipped_table_with_area_column():
    output = render_business(_sample_categorized(), generated_at=_FROZEN_STAMP)
    assert "## What shipped" in output
    assert "| Area | What shipped |" in output
    assert "| Infra | Established the per-sprint Dev-to-UAT release tracker. |" in output
    assert "| Frontend | Improved how funding paper sections are displayed so users see the full output. |" in output


def test_business_output_strips_keys_and_work_type_tags():
    """The flat bullets reflect what's in the (post-polish) ticket summaries.

    The renderer itself does not add FP-XXX or [sprint] markers; the business
    doc only ever shows what the polish step left. Verify the renderer does
    not inject those markers from BundleTicket metadata.
    """
    output = render_business(_sample_categorized(), generated_at=_FROZEN_STAMP)
    assert "FP-185" not in output  # key not leaked into business doc
    assert "FP-156" not in output
    assert "[sprint]" not in output
    assert "[tech-debt]" not in output


def test_renders_audit_footer():
    output = render_business(_sample_categorized(), generated_at=_FROZEN_STAMP)
    assert "`/release-doc FP-194 --audience business`" in output
    assert f"**Generated at:** {_FROZEN_STAMP}" in output
    assert "[FP-194](https://ltads.atlassian.net/browse/FP-194)" in output


def test_renders_business_pie_after_summary():
    output = render_business(_sample_categorized(), generated_at=_FROZEN_STAMP)
    assert "## What shipped — at a glance" in output
    assert "pie title What shipped" in output


def test_renders_business_mindmap_with_emojis():
    output = render_business(_sample_categorized(), generated_at=_FROZEN_STAMP)
    assert "mindmap" in output
    assert "root((v0.4.6))" in output
    # Frontend + Infra each have one ticket in the fixture.
    assert "🎨 Frontend (1)" in output
    assert "🏗️ Infra (1)" in output


def test_business_visuals_placed_before_talking_points():
    output = render_business(_sample_categorized(), generated_at=_FROZEN_STAMP)
    glance_idx = output.index("## What shipped — at a glance")
    talking_idx = output.index("## Talking points")
    assert glance_idx < talking_idx
