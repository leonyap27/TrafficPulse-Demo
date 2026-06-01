"""Algorithmic spec for the /release-cut slash command (FP-214).

This module is the **canonical, tested contract** for the release-cut logic.
The slash command (.claude/commands/release-cut.md) re-implements this logic in
its markdown prose using MCP tool calls. Unit tests pin the algorithms here;
skill prose is tested via the executable spec.

Two modes driven by the slash-command invocation:
    PREVIEW  — read-only, ephemeral, chat-only. Shows the decision table so the
               operator can inspect the bundle state before committing to a cut.
    CUT      — writes VERSION file, promotes the sprint draft, creates JIRA
               artefacts, and commits on a chore branch. Interactive: one
               carry-over prompt per non-DONE bundle item.

Command shapes handled by the slash command (not this module):
    /release-cut               → PREVIEW
    /release-cut YES           → CUT (default patch bump)
    /release-cut 0.5.0 YES     → CUT (explicit version)
    /release-cut 0.5.0         → PREVIEW (explicit version preview)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from scripts.release_docs.next_tracker import bump_patch

# ---------------------------------------------------------------------------
# Public data types
# ---------------------------------------------------------------------------

BundleItemStatus = Literal[
    "DONE",
    "READY FOR DEPLOY",
    "In Progress",
    "In Review",
    "TESTING",
    "To Do",
    "Backlog",
]

CarryOverDecision = Literal["Y", "drop", "skip"]

DONE_STATUSES: frozenset[str] = frozenset({"DONE", "READY FOR DEPLOY"})
"""Statuses considered complete for carry-over scan purposes.

Items in these statuses are counted as shipped and excluded from the
carry-over prompt. Items in any other status are carry-over candidates.
"""


@dataclass(frozen=True)
class BundleItem:
    """One item from the tracker's ## Bundle section."""

    key: str
    summary: str
    status: str
    work_type: str
    sprint: str | None = None
    has_doc: bool = False


@dataclass
class CarryOverCandidate:
    """A bundle item eligible for carry-over, with the operator's decision."""

    item: BundleItem
    decision: CarryOverDecision | None = None


@dataclass
class PreviewRow:
    """One row in the PREVIEW decision table."""

    key: str
    summary: str
    status: str
    work_type: str
    sprint_contaminated: bool
    outcome: str


@dataclass
class CutSummary:
    """Output of a completed release cut."""

    current_version: str
    next_version: str
    current_tracker_key: str
    next_tracker_key: str
    carry_overs: list[BundleItem] = field(default_factory=list)
    dropped: list[BundleItem] = field(default_factory=list)
    draft_promoted: bool = False
    draft_path: Path | None = None
    to_follow_up: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Version helpers
# ---------------------------------------------------------------------------

_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def validate_version(version: str) -> str:
    """Return ``version`` unchanged if it is a valid MAJOR.MINOR.PATCH string.

    Args:
        version: Semver string to validate (e.g. ``"0.5.0"``).

    Returns:
        The input string unchanged.

    Raises:
        ValueError: If the string does not match MAJOR.MINOR.PATCH with
            three non-negative integer segments.
    """
    v = version.strip()
    if not _SEMVER_RE.match(v):
        raise ValueError(
            f"Invalid semver {version!r}: expected MAJOR.MINOR.PATCH "
            "(three dot-separated non-negative integers, no pre-release suffix)."
        )
    return v


def resolve_next_version(current_version: str, explicit: str | None) -> str:
    """Return the next version to use for the release cut.

    Args:
        current_version: Current version read from the ``VERSION`` file
            (plain MAJOR.MINOR.PATCH, no trailing newline).
        explicit: Caller-supplied override (e.g. from ``/release-cut 0.5.0``).
            If not ``None``, validated and returned verbatim.

    Returns:
        Next version string (MAJOR.MINOR.PATCH).

    Raises:
        ValueError: If ``explicit`` is given but is not a valid semver, or if
            ``current_version`` cannot be bumped.
    """
    if explicit is not None:
        return validate_version(explicit)
    return bump_patch(current_version.strip())


# ---------------------------------------------------------------------------
# Bundle parsing
# ---------------------------------------------------------------------------

# Table-format bundle row: | [FP-XXX](url) | summary | type | status | Y/N |
# Groups: 1=key, 2=summary, 3=work_type, 4=document-flag ("Y" or "")
_BUNDLE_TABLE_ROW_RE = re.compile(
    r"^\|\s*\[?(FP-\d+)\]?(?:\([^)]*\))?\s*"  # col 1: key
    r"\|\s*(.+?)\s*"                            # col 2: summary (group 2)
    r"\|\s*(.+?)\s*"                            # col 3: type/work_type (group 3)
    r"\|\s*[^|]*\s*"                            # col 4: status (ignored — live status fetched from JIRA)
    r"\|\s*(Y?)\s*\|",                          # col 5: Document Y/N (group 4)
    re.MULTILINE,
)

# Legacy checklist-format row: - [ ] FP-XXX [type] summary
_BUNDLE_LINE_RE = re.compile(
    r"^\s*-\s+\[[ x]\]\s+(FP-\d+)\s+\[([^\]]+)\]\s+(.+?)\s*$",
    re.MULTILINE,
)


def parse_bundle_lines(description: str) -> list[tuple[str, str, str, bool]]:
    """Extract ``(key, work_type, summary, has_doc)`` tuples from a tracker description.

    Supports both the current table format and the legacy checklist format.
    Table format is tried first; checklist is used as a fallback for older
    trackers that have not been migrated.

    Table format (canonical)::

        | Jira ID | Desc | Type | Status | Document (Y/N) |
        | --- | --- | --- | --- | --- |
        | [FP-XXX](url) | summary | sprint | In Progress | Y |

    Legacy checklist format::

        - [ ] FP-XXX [work-type] <summary>

    ``has_doc`` is ``True`` when the Document column contains ``"Y"``.
    For legacy checklist rows, ``has_doc`` is always ``False``.

    Args:
        description: Full tracker description markdown.

    Returns:
        List of ``(fp_key, work_type, summary, has_doc)`` tuples in document order.
    """
    table_results = [
        (m.group(1), m.group(3).strip(), m.group(2).strip(), m.group(4).strip() == "Y")
        for m in _BUNDLE_TABLE_ROW_RE.finditer(description)
    ]
    if table_results:
        return table_results

    # Fall back to legacy checklist format
    return [
        (m.group(1), m.group(2).strip(), m.group(3).strip(), False)
        for m in _BUNDLE_LINE_RE.finditer(description)
    ]


def auto_carry_all(items: list[BundleItem]) -> list[BundleItem]:
    """Return all non-DONE items as automatic carry-overs (no prompt required).

    This is the new carry-over policy (replacing the interactive Y/drop/skip
    prompt): every item not in ``DONE_STATUSES`` is carried forward to the
    next tracker without operator input. Items in ``READY FOR DEPLOY`` are
    considered shipped (they appear in ``DONE_STATUSES``).

    Args:
        items: All bundle items with live JIRA status.

    Returns:
        Carry-over items in input order.
    """
    return [item for item in items if item.status not in DONE_STATUSES]


# ---------------------------------------------------------------------------
# Sprint contamination detection
# ---------------------------------------------------------------------------


def detect_sprint_contamination(
    items: list[BundleItem],
    current_sprint: str | None,
) -> list[BundleItem]:
    """Return items whose sprint does not match the current sprint.

    An item is "contaminated" (came from a different sprint) when both its
    ``sprint`` field is non-None and differs from ``current_sprint``.

    Args:
        items: Bundle items with sprint metadata populated from JIRA.
        current_sprint: The sprint name/id expected for this bundle (e.g.
            ``"Sprint 2"``). If ``None`` (unknown), no items are flagged.

    Returns:
        Subset of ``items`` considered cross-sprint contaminated.
    """
    if current_sprint is None:
        return []
    return [
        item
        for item in items
        if item.sprint is not None and item.sprint != current_sprint
    ]


# ---------------------------------------------------------------------------
# PREVIEW table
# ---------------------------------------------------------------------------


def build_preview_table(
    items: list[BundleItem],
    current_version: str,
    next_version: str,
    current_sprint: str | None = None,
) -> list[PreviewRow]:
    """Build the PREVIEW decision table rows.

    Each row shows what would happen to that item if ``/release-cut YES`` ran
    right now. Contaminated items are flagged with ``sprint_contaminated=True``
    so the slash command can add a warning symbol in the rendered table.

    Args:
        items: Bundle items with live JIRA status.
        current_version: Current sprint's version (e.g. ``"0.4.5"``).
        next_version: Proposed next version (e.g. ``"0.4.6"``).
        current_sprint: Sprint name used for contamination detection. ``None``
            disables sprint-contamination flagging.

    Returns:
        List of ``PreviewRow`` objects in input order.
    """
    contaminated_keys = {
        item.key for item in detect_sprint_contamination(items, current_sprint)
    }
    rows = []
    for item in items:
        in_done = item.status in DONE_STATUSES
        contaminated = item.key in contaminated_keys
        if in_done:
            outcome = f"✓ ships in v{current_version}"
        else:
            outcome = f"carry-over → v{next_version} (status: {item.status})"
        rows.append(
            PreviewRow(
                key=item.key,
                summary=item.summary,
                status=item.status,
                work_type=item.work_type,
                sprint_contaminated=contaminated,
                outcome=outcome,
            )
        )
    return rows


def render_preview_markdown(
    rows: list[PreviewRow],
    current_version: str,
    next_version: str,
    current_tracker_key: str,
) -> str:
    """Render the PREVIEW table as a markdown string for chat output.

    Args:
        rows: Output of ``build_preview_table``.
        current_version: Current version string.
        next_version: Proposed next version string.
        current_tracker_key: Active tracker key (e.g. ``"FP-194"``).

    Returns:
        Markdown string suitable for display in the Claude Code chat pane.
        Purely cosmetic — does not write any files or call any APIs.
    """
    lines = [
        f"## PREVIEW — `/release-cut` (no writes)",
        f"",
        f"**Current tracker:** {current_tracker_key} (v{current_version})",
        f"**Proposed next version:** v{next_version}",
        f"",
        f"| Ticket | Summary | Status | Work type | Sprint flag | If cut now |",
        f"|---|---|---|---|---|---|",
    ]
    for row in rows:
        flag = "⚠️ cross-sprint" if row.sprint_contaminated else "—"
        lines.append(
            f"| {row.key} | {row.summary[:50]} | {row.status} "
            f"| [{row.work_type}] | {flag} | {row.outcome} |"
        )
    lines += [
        "",
        "_No files or JIRA records have been changed._",
        "_Re-run `/release-cut` any time — each run is fresh._",
        "_Run `/release-cut YES` (or `/release-cut <version> YES`) to perform the actual cut._",
    ]
    if any(row.sprint_contaminated for row in rows):
        lines.insert(
            3,
            "> ⚠️  **Sprint contamination detected** — one or more items below "
            "belong to a different sprint. Review before cutting.",
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Draft promotion
# ---------------------------------------------------------------------------

_DRAFT_GLOB = "v*_draft.md"
RELEASES_DIR = Path("docs/3.0-deployment/releases")


def locate_draft(releases_dir: Path, current_version: str) -> Path | None:
    """Return the path to the version-specific draft file, or ``None``.

    Looks for ``docs/3.0-deployment/releases/v<current_version>_draft.md``.
    Does NOT fall back to other draft filenames — the file naming convention
    is ``v<version>_draft.md`` as established in the FP-214 review.

    Args:
        releases_dir: Base directory (normally
            ``docs/3.0-deployment/releases``).
        current_version: Current sprint version string (e.g. ``"0.4.5"``).

    Returns:
        ``Path`` to the draft file if it exists, ``None`` otherwise.
    """
    candidate = releases_dir / f"v{current_version}_draft.md"
    return candidate if candidate.exists() else None


def promote_draft(
    releases_dir: Path,
    current_version: str,
) -> tuple[bool, Path | None, str | None]:
    """Rename ``v<current>_draft.md`` to ``v<current>.md`` in-place.

    This is the "promotion" step at sprint close: the running draft becomes
    the canonical release notes file for that version.

    Args:
        releases_dir: Base directory (normally
            ``docs/3.0-deployment/releases``).
        current_version: Current sprint version (e.g. ``"0.4.5"``).

    Returns:
        A three-tuple ``(promoted, dest_path, skip_reason)`` where:
        - ``promoted`` is ``True`` when the rename succeeded.
        - ``dest_path`` is the ``Path`` of the new file when ``promoted``.
        - ``skip_reason`` is a human-readable message when ``promoted`` is
          ``False`` (draft not found or destination already exists).
    """
    draft = locate_draft(releases_dir, current_version)
    if draft is None:
        return (
            False,
            None,
            f"No v{current_version}_draft.md found in {releases_dir}. "
            "Sprint release notes were not assembled incrementally — "
            "create docs/3.0-deployment/releases/"
            f"v{current_version}_draft.md manually, or run /jira-done on "
            "each READY FOR DEPLOY ticket to build it.",
        )
    dest = releases_dir / f"v{current_version}.md"
    if dest.exists():
        return (
            False,
            dest,
            f"{dest} already exists — draft promotion skipped to avoid overwrite. "
            "Remove the existing file if you want to re-promote.",
        )
    draft.rename(dest)
    return (True, dest, None)


# ---------------------------------------------------------------------------
# Carry-over scan helpers
# ---------------------------------------------------------------------------


def collect_carry_over_candidates(items: list[BundleItem]) -> list[CarryOverCandidate]:
    """Return items that need a carry-over decision (not in DONE_STATUSES).

    Args:
        items: All bundle items with live JIRA status.

    Returns:
        ``CarryOverCandidate`` wrappers for non-done items, decision=None.
    """
    return [
        CarryOverCandidate(item=item)
        for item in items
        if item.status not in DONE_STATUSES
    ]


def apply_decisions(
    candidates: list[CarryOverCandidate],
) -> tuple[list[BundleItem], list[BundleItem]]:
    """Split candidates into (carry_overs, dropped) based on their decision.

    Candidates with ``decision == "skip"`` or ``decision is None`` are treated
    as unresolved — the caller should not call this function until all
    decisions are confirmed.

    Args:
        candidates: List with all ``decision`` fields set to ``"Y"`` or
            ``"drop"`` (no ``None`` or ``"skip"`` entries allowed here).

    Returns:
        ``(carry_overs, dropped)`` lists of ``BundleItem`` objects.

    Raises:
        ValueError: If any candidate has ``decision`` that is not ``"Y"`` or
            ``"drop"``.
    """
    carry_overs, dropped = [], []
    for c in candidates:
        if c.decision == "Y":
            carry_overs.append(c.item)
        elif c.decision == "drop":
            dropped.append(c.item)
        else:
            raise ValueError(
                f"Unresolved carry-over decision for {c.item.key}: {c.decision!r}. "
                "All candidates must be answered Y or drop before applying."
            )
    return carry_overs, dropped


# ---------------------------------------------------------------------------
# VERSION file helpers
# ---------------------------------------------------------------------------

VERSION_FILE = Path("VERSION")


def read_version(version_file: Path = VERSION_FILE) -> str:
    """Read and return the current version string from the VERSION file.

    Args:
        version_file: Path to the ``VERSION`` file (default: repo root).

    Returns:
        Version string with whitespace stripped (e.g. ``"0.4.5"``).

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file content is not a valid semver.
    """
    content = version_file.read_text(encoding="utf-8").strip()
    return validate_version(content)


def write_version(new_version: str, version_file: Path = VERSION_FILE) -> None:
    """Overwrite the VERSION file with ``new_version`` followed by a newline.

    Args:
        new_version: Valid semver string (validated before writing).
        version_file: Path to the ``VERSION`` file (default: repo root).

    Raises:
        ValueError: If ``new_version`` is not a valid semver.
    """
    validate_version(new_version)
    version_file.write_text(new_version + "\n", encoding="utf-8")
