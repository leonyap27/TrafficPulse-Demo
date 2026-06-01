"""Render a business-audience release doc from a ``CategorizedRelease``.

Audience: managers, stakeholders, exec briefings. Strips engineering detail
(FP-XXX keys, work-type tags, PR references, test evidence, readiness
checklist, rollback) and surfaces three layered views of the release:

1. ``Summary`` — the team's narrative bullets from the tracker (manual prose).
2. ``Talking points`` — LLM-distilled high-level outcomes (3–5 bullets).
3. ``What shipped`` — every change as a flat outcome-framed bullet (no buckets,
   no keys — the polish step strips them when audience="business").

The renderer is pure: input is the categorized release plus any pre-distilled
talking points; output is markdown. The CLI is responsible for running polish
with ``audience="business"`` and calling ``distill_talking_points`` before
handing the data to this renderer.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from .models import CategorizedRelease
from .visuals import build_business_mindmap, build_business_pie

_PACKAGE_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _PACKAGE_DIR.parent.parent
DEFAULT_BUSINESS_TEMPLATE_PATH = (
    _REPO_ROOT / "docs" / "3.0-deployment" / "business-release-template.md"
)


def render_business(
    categorized: CategorizedRelease,
    *,
    talking_points: list[str] | None = None,
    generated_at: str | None = None,
    template_path: Path | None = None,
) -> str:
    """Render a business-audience release document to markdown.

    Args:
        categorized: Categorized release data. Ticket summaries should already
            be business-polished (run ``polish(..., audience="business")``
            beforehand). The renderer flattens all buckets into one list.
        talking_points: Pre-distilled talking points. Empty/None renders a
            placeholder pointing the reader at ``--polish``.
        generated_at: ISO-8601 timestamp for the footer. Defaults to now (UTC).
        template_path: Override the business template path.

    Returns:
        Rendered markdown for the business-audience release doc.
    """
    template_file = template_path or DEFAULT_BUSINESS_TEMPLATE_PATH
    env = Environment(
        loader=FileSystemLoader(template_file.parent),
        autoescape=select_autoescape(disabled_extensions=("md",), default=False),
        keep_trailing_newline=True,
        undefined=StrictUndefined,
    )
    template = env.get_template(template_file.name)

    stamp = generated_at or datetime.now(timezone.utc).isoformat()
    release_input = categorized.input

    # Business doc flattens every ticket into (area, summary) rows, preserving
    # BUCKET_ORDER so the table groups related work visually.
    all_rows = [
        (bucket.bucket, ticket.summary)
        for bucket in categorized.buckets
        for ticket in bucket.tickets
    ]

    business_pie = build_business_pie(categorized.buckets)
    business_mindmap = build_business_mindmap(
        release_input.manifest.version, categorized.buckets
    )

    return template.render(
        tracker_key=release_input.tracker_key,
        tracker_url=release_input.tracker_url,
        manifest=release_input.manifest,
        change_summary=release_input.change_summary,
        talking_points=talking_points or [],
        all_rows=all_rows,
        carry_over=release_input.carry_over,
        generated_at=stamp,
        business_pie=business_pie,
        business_mindmap=business_mindmap,
    )
