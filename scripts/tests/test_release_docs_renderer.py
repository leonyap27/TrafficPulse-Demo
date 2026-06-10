"""Tests for scripts/release_docs/renderer.py.

End-to-end: build a small ``ReleaseInput`` → categorize → render → assert that
the rendered markdown contains the expected section structure and bullets.
Snapshot-style equality is intentionally avoided; specific assertions resist
spurious test failures from cosmetic template tweaks.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from release_docs.categorizer import categorize_bundle  # noqa: E402
from release_docs.models import (  # noqa: E402
    BundleTicket,
    CategorizedRelease,
    PRReference,
    ReadinessItem,
    ReleaseInput,
    ReleaseManifest,
    EvidenceLink,
)
from release_docs.renderer import render  # noqa: E402

_FROZEN_STAMP = "2026-05-25T14:00:00+08:00"


def _sample_input(*, known_issues: list[str] | None = None) -> ReleaseInput:
    return ReleaseInput(
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
            "Adds the Dev-to-UAT release tracker pilot.",
            "Bakes in the versioning standard.",
        ],
        bundle=[
            BundleTicket(
                key="FP-185",
                work_type="sprint",
                summary="Design Jira Dev-to-UAT change tracker",
                parent_epic_key="FP-89",
            ),
            BundleTicket(
                key="FP-156",
                work_type="sprint",
                summary="Sections layout view neatly without scrolling",
                components=["frontend"],
            ),
            BundleTicket(
                key="FP-184",
                work_type="tech-debt",
                summary="Strip default compute SA project-role grants",
                labels=["security"],
            ),
        ],
        pr_references=[
            PRReference(repo="leonyap27/Funding_paper_agent", pr_number=25),
            PRReference(commit_sha="fbf5523", note="release base on dev"),
        ],
        readiness=[
            ReadinessItem(label="Code freeze on dev", status="passed"),
            ReadinessItem(label="Approver sign-off", status="pending"),
        ],
        test_evidence=[
            EvidenceLink(
                label="FP-185 /jira-test evidence",
                url="https://ltads.atlassian.net/browse/FP-185?focusedCommentId=1",
            ),
        ],
        known_issues=known_issues or [],
        previous_version="0.4.5",
    )


def _render(release_input: ReleaseInput) -> str:
    categorized = CategorizedRelease(
        input=release_input,
        buckets=categorize_bundle(release_input.bundle),
    )
    return render(categorized, generated_at=_FROZEN_STAMP)


def test_renders_release_header():
    output = _render(_sample_input())
    assert "# Release v0.4.6 → UAT" in output
    assert "**Tracker:** [FP-194](https://ltads.atlassian.net/browse/FP-194)" in output
    assert "**Release date:** 2026-05-27" in output
    assert "**Approver:** Leon Ye" in output
    assert "**Sprint:** Sprint 1 (12 May - 26 May 2026)" in output


def test_renders_change_summary_bullets():
    output = _render(_sample_input())
    assert "- Adds the Dev-to-UAT release tracker pilot." in output
    assert "- Bakes in the versioning standard." in output


def test_renders_buckets_in_canonical_order():
    output = _render(_sample_input())
    front_idx = output.index("### Frontend")
    infra_idx = output.index("### Infra")
    security_idx = output.index("### Security")
    assert front_idx < infra_idx < security_idx


def test_renders_ticket_bullets_with_link_and_work_type():
    output = _render(_sample_input())
    assert (
        "- **[FP-185](https://ltads.atlassian.net/browse/FP-185)** _[sprint]_ — "
        "Design Jira Dev-to-UAT change tracker"
    ) in output
    assert (
        "- **[FP-184](https://ltads.atlassian.net/browse/FP-184)** _[tech-debt]_ — "
        "Strip default compute SA project-role grants"
    ) in output


def test_renders_readiness_checkbox_state():
    output = _render(_sample_input())
    assert "- [x] Code freeze on dev" in output
    assert "- [ ] Approver sign-off" in output


def test_renders_pr_and_commit_references():
    output = _render(_sample_input())
    assert "- leonyap27/Funding_paper_agent#25" in output
    assert "- commit `fbf5523` — release base on dev" in output


def test_renders_known_issues_none_when_empty():
    output = _render(_sample_input(known_issues=[]))
    assert "## Known issues / limitations" in output
    assert "None reported." in output


def test_renders_known_issues_bullets_when_present():
    output = _render(_sample_input(known_issues=["Slow first load on UAT"]))
    assert "## Known issues / limitations" in output
    assert "- Slow first load on UAT" in output
    assert "None reported." not in output


def test_renders_rollback_section_with_previous_version():
    output = _render(_sample_input())
    assert "## Rollback" in output
    assert "Previous version: `v0.4.5`" in output


def test_renders_audit_footer():
    output = _render(_sample_input())
    assert "**Generated by:** `/release-doc FP-194`" in output
    assert f"**Generated at:** {_FROZEN_STAMP}" in output


def _render_with_extras(release_input, extras: str | None) -> str:
    from release_docs.renderer import render

    categorized = CategorizedRelease(
        input=release_input,
        buckets=categorize_bundle(release_input.bundle),
    )
    return render(categorized, generated_at=_FROZEN_STAMP, extras_content=extras)


def test_renders_at_a_glance_section_with_components_mermaid():
    output = _render(_sample_input())
    assert "## At a glance" in output
    assert "```mermaid" in output
    assert "flowchart LR" in output
    assert "R([Release v0.4.6])" in output


def test_at_a_glance_sits_between_summary_and_what_shipped():
    output = _render(_sample_input())
    summary_idx = output.index("## Summary")
    glance_idx = output.index("## At a glance")
    shipped_idx = output.index("## What shipped")
    assert summary_idx < glance_idx < shipped_idx


def test_extras_content_injected_verbatim_when_provided():
    extras = "### Workflow\n\n```mermaid\nsequenceDiagram\n    A->>B: hi\n```"
    output = _render_with_extras(_sample_input(), extras)
    assert extras in output
    # Extras must come AFTER the components diagram, BEFORE What shipped.
    glance_idx = output.index("## At a glance")
    extras_idx = output.index("### Workflow")
    shipped_idx = output.index("## What shipped")
    assert glance_idx < extras_idx < shipped_idx


def test_no_extras_section_when_extras_omitted():
    output = _render_with_extras(_sample_input(), None)
    # No phantom "### Workflow" / sequenceDiagram / swimlane / Decision points
    # appears when the host LLM passed no extras (covers FP-200 AC4).
    assert "sequenceDiagram" not in output
    assert "Decision points" not in output
