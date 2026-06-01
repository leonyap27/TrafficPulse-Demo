"""Build the description body for the next sprint's release-tracker JIRA issue.

Used by ``/release-doc <tracker> YES`` at sprint close. The slash command
orchestrator calls :func:`build_next_tracker_body` with the carry-over items,
the next version, and the manifest fields it wants to inherit from the
current tracker, then passes the returned markdown to ``createJiraIssue``.

Kept separate from the release-doc renderer so next-tracker creation can be
tested independently and so it doesn't accidentally inherit talking-points
polish (which is renderer-specific and would be wrong on an empty bundle).
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from .models import CarryOverTicket

_PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULT_TRACKER_TEMPLATE_PATH = _PACKAGE_DIR / "TRACKER_TEMPLATE.md"


def build_next_tracker_body(
    *,
    prev_tracker_key: str,
    next_version: str,
    target_env_detail: str,
    approver: str,
    carry_over: list[CarryOverTicket],
    template_path: Path | None = None,
) -> str:
    """Build the markdown body for the next sprint's release-tracker issue.

    Args:
        prev_tracker_key: The tracker that just closed (e.g. ``"FP-194"``).
            Surfaced in provenance text so future readers can trace this
            tracker's origin back to the previous sprint's close event.
        next_version: Semver string for the next release (e.g. ``"0.4.7"``).
            By default the PATCH increment of the previous tracker's version.
        target_env_detail: Long form target environment (e.g.
            ``"UAT (Cloud Run: funding-paper-agent)"``) inherited from the
            previous tracker so deployment intent stays explicit.
        approver: Approver / tech lead, inherited from the previous tracker.
        carry_over: Bundle items that did not reach ``DONE`` this sprint and
            are rolled forward into the new tracker's bundle. Empty list is
            fine — the template renders a "sprint planning will add items"
            placeholder.
        template_path: Override path for testing.

    Returns:
        Rendered markdown ready to pass to ``createJiraIssue`` as the issue
        description (with ``contentFormat: "markdown"`` and ``labels`` including
        ``"release-tracker"``).
    """
    template_file = template_path or DEFAULT_TRACKER_TEMPLATE_PATH
    env = Environment(
        loader=FileSystemLoader(template_file.parent),
        autoescape=select_autoescape(disabled_extensions=("md",), default=False),
        keep_trailing_newline=True,
        undefined=StrictUndefined,
    )
    template = env.get_template(template_file.name)
    return template.render(
        prev_tracker_key=prev_tracker_key,
        next_version=next_version,
        target_env_detail=target_env_detail,
        approver=approver,
        carry_over=carry_over,
    )


def bump_patch(version: str) -> str:
    """Return the version with PATCH incremented by one.

    ``"0.4.6"`` → ``"0.4.7"``. Strips any pre-release suffix (``"-rc.1"``).
    Per VERSIONING.md, this is the default next-version derivation when
    rolling from sprint N to sprint N+1 in dev; an explicit
    ``--next-version`` arg can override (e.g. for a UAT-promote MINOR bump).

    Args:
        version: Semver string ``MAJOR.MINOR.PATCH`` (with optional
            ``-suffix``). Examples: ``"0.4.6"``, ``"0.4.6-rc.1"``.

    Returns:
        Next-patch version string, no pre-release suffix.

    Raises:
        ValueError: If ``version`` doesn't match ``MAJOR.MINOR.PATCH``.
    """
    base = version.split("-", 1)[0]
    parts = base.split(".")
    if len(parts) != 3:
        raise ValueError(
            f"Expected MAJOR.MINOR.PATCH, got {version!r}. "
            "Strip suffix and ensure three dot-separated integers."
        )
    try:
        major, minor, patch = (int(p) for p in parts)
    except ValueError as exc:
        raise ValueError(
            f"Non-integer segment in {version!r}: each of MAJOR/MINOR/PATCH "
            "must be an integer."
        ) from exc
    return f"{major}.{minor}.{patch + 1}"
