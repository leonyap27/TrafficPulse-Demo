"""Mermaid + table builders for release-document visuals (FP-200).

Pure functions: input is the already-categorized release data, output is a
markdown string ready to drop into a Jinja template. No selection logic lives
here — the host LLM (Claude Code / Codex) running ``/release-doc`` decides
which extra primitives (sequence / swimlane / decision-table) to render and
passes them through to the renderer as a pre-composed markdown blob. This
module only owns the deterministic, always-on builders.

Always-on builders (no host-LLM judgement involved):
    * ``build_components_mermaid`` — technical doc, bucket → ticket-count
      flowchart between ``## Summary`` and ``## What shipped``.
    * ``build_business_pie`` — business doc, mermaid ``pie`` chart of
      bucket → count.
    * ``build_business_mindmap`` — business doc, mermaid ``mindmap`` with
      emoji-per-bucket labels.
"""

from __future__ import annotations

from .models import Bucket, CategorizedBucket

_BUCKET_EMOJI: dict[Bucket, str] = {
    "Frontend": "🎨",
    "Backend": "⚙️",
    "Agents+RAG": "🤖",
    "Infra": "🏗️",
    "Security": "🔒",
    "Docs": "📝",
    "Other": "📦",
}


def build_components_mermaid(version: str, buckets: list[CategorizedBucket]) -> str:
    """Always-on technical-doc diagram: bucket → ticket-count flowchart.

    Renders a left-to-right flowchart with the release at the root and one
    child node per non-empty bucket, labelled ``<Bucket>\\n<N> changes``.
    Engineers see the bucket spread at a glance; the full FP-XXX bullet list
    below provides per-ticket detail.

    Args:
        version: Release version (e.g. ``"0.4.6"``) for the root node label.
        buckets: Categorized buckets in canonical order. Empty buckets are
            already filtered by ``categorize_bundle``.

    Returns:
        Mermaid markdown block (fenced) ready to inject into the template.
        Returns an empty string when ``buckets`` is empty (defensive — should
        not happen in practice; the renderer's pipeline filters empties).
    """
    if not buckets:
        return ""
    lines = ["```mermaid", "flowchart LR", f"    R([Release v{version}])"]
    for idx, bucket in enumerate(buckets):
        node_id = f"B{idx}"
        count_label = f"{len(bucket.tickets)} change{'s' if len(bucket.tickets) != 1 else ''}"
        lines.append(f"    R --> {node_id}[{bucket.bucket}<br/>{count_label}]")
    lines.append("```")
    return "\n".join(lines)


def build_business_pie(buckets: list[CategorizedBucket]) -> str:
    """Always-on business-doc pie chart of bucket → count.

    Proportional view — readers see at a glance which area dominated the
    release. Mermaid ``pie`` renders in GitHub web and JIRA-cloud markdown
    surfaces.

    Args:
        buckets: Categorized buckets in canonical order.

    Returns:
        Mermaid pie block (fenced). Empty string if no buckets.
    """
    if not buckets:
        return ""
    lines = ["```mermaid", "pie title What shipped"]
    for bucket in buckets:
        lines.append(f'    "{bucket.bucket}" : {len(bucket.tickets)}')
    lines.append("```")
    return "\n".join(lines)


def build_business_mindmap(version: str, buckets: list[CategorizedBucket]) -> str:
    """Always-on business-doc mindmap with emoji-per-bucket labels.

    Labelled-by-area view — sits next to the pie so readers get both a
    proportional sense (pie) and a named-by-area sense (mindmap). Mermaid
    ``mindmap`` is supported in mermaid 9.x+ which GitHub and JIRA both ship.

    Args:
        version: Release version for the root node label.
        buckets: Categorized buckets in canonical order.

    Returns:
        Mermaid mindmap block (fenced). Empty string if no buckets.
    """
    if not buckets:
        return ""
    lines = ["```mermaid", "mindmap", f"  root((v{version}))"]
    for bucket in buckets:
        emoji = _BUCKET_EMOJI.get(bucket.bucket, "📦")
        lines.append(f"    {emoji} {bucket.bucket} ({len(bucket.tickets)})")
    lines.append("```")
    return "\n".join(lines)
