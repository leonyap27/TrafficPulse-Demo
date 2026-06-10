"""Render a ``CategorizedRelease`` into release-document markdown via Jinja2."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from .models import CategorizedRelease
from .visuals import build_components_mermaid

# Repo-relative path to the canonical template. Resolved from this file so the
# package works regardless of caller cwd.
_PACKAGE_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _PACKAGE_DIR.parent.parent
DEFAULT_TEMPLATE_PATH = _REPO_ROOT / "docs" / "3.0-deployment" / "release-doc-template.md"


def render(
    categorized: CategorizedRelease,
    *,
    generated_at: str | None = None,
    template_path: Path | None = None,
    extras_content: str | None = None,
) -> str:
    """Render the release document to markdown.

    Args:
        categorized: Categorized release data (output of ``categorize_bundle``
            wrapped with the original ``ReleaseInput``).
        generated_at: ISO-8601 timestamp string to stamp into the audit footer.
            Defaults to the current UTC time when omitted.
        template_path: Override path to a Jinja2 template. Defaults to the
            canonical template under ``docs/3.0-deployment/``.
        extras_content: Pre-composed markdown blob containing extra visuals
            (sequence diagram, swimlane, decision table). The host LLM
            orchestrating ``/release-doc`` decides whether to include any
            extras and writes the blob; the renderer injects it verbatim
            between the always-on components diagram and ``## What shipped``.
            When ``None`` or empty, no extras section is emitted (covers
            FP-200 AC4 — bugfix-only bundles get no forced empty diagrams).

    Returns:
        Rendered markdown document.

    Raises:
        FileNotFoundError: If ``template_path`` does not exist.
        jinja2.UndefinedError: If the template references a field that is not
            present in the input (strict-undefined catches schema drift).
    """
    template_file = template_path or DEFAULT_TEMPLATE_PATH
    env = Environment(
        loader=FileSystemLoader(template_file.parent),
        autoescape=select_autoescape(disabled_extensions=("md",), default=False),
        keep_trailing_newline=True,
        undefined=StrictUndefined,
    )
    template = env.get_template(template_file.name)

    stamp = generated_at or datetime.now(timezone.utc).isoformat()
    release_input = categorized.input
    components_mermaid = build_components_mermaid(
        release_input.manifest.version, categorized.buckets
    )
    return template.render(
        tracker_key=release_input.tracker_key,
        tracker_url=release_input.tracker_url,
        jira_base_url=release_input.jira_base_url.rstrip("/"),
        manifest=release_input.manifest,
        change_summary=release_input.change_summary,
        buckets=categorized.buckets,
        pr_references=release_input.pr_references,
        readiness=release_input.readiness,
        test_evidence=release_input.test_evidence,
        known_issues=release_input.known_issues,
        previous_version=release_input.previous_version,
        carry_over=release_input.carry_over,
        generated_at=stamp,
        components_mermaid=components_mermaid,
        extras_content=extras_content or "",
    )
