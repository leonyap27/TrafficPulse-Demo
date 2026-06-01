"""Active release-tracker helpers for the /jira-impl and /jira-test skills.

This module is the **canonical, tested contract** for the active-tracker resolution +
section-mutation behavior described in FP-212. The slash-command skills
(`.claude/commands/jira-impl.md`, `.claude/commands/jira-test.md`) re-implement this
logic in their markdown prose using MCP tool calls (`searchJiraIssuesUsingJql` +
`getJiraIssue` + `editJiraIssue`).

Per FP-212 review Q1=B, the skills do NOT shell out to this module at runtime — it
exists so the algorithms have an executable spec with unit tests. The trade-off is
documented and accepted: skill prose can drift from this module silently, but unit
tests still pin the algorithmic contract.

Behavior summary (set in FP-212 review):
    Q2: missing tracker → /jira-impl STOPs, /jira-test skips (best-effort).
    Q3: evidence line is upserted per ticket (one line per FP-XXX on the tracker).
    Q4: bundle line uses single-space formatting: `- [ ] FP-XXX [work-type] <summary>`.
    Q5: missing section auto-repaired with stable anchor; fuzzy-match heading raises
        SchemaDriftError so the skill can ask the operator to reconcile.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

WORK_TYPE_PRECEDENCE: tuple[str, ...] = ("tech-debt", "carry-over")
"""Order in which `release-work-type:*` labels resolve when multiple are present."""

JIRA_BASE_URL: str = "https://ltads.atlassian.net/browse"
"""Base URL for JIRA issue links in bundle table rows."""

BUNDLE_HEADER: str = "Bundle"
"""Canonical bundle section header word (matched as a prefix, case-insensitive)."""

TEST_EVIDENCE_HEADER: str = "Test evidence"
"""Canonical test-evidence section header word (matched as a prefix, case-insensitive)."""

# Words that signal an operator-renamed bundle/evidence section. Hitting one of these
# on a heading other than the canonical name signals intentional restructure
# (hard-stop) rather than accidental deletion (auto-repair).
_BUNDLE_FUZZY_KEYWORDS: tuple[str, ...] = ("bundle", "items", "tickets", "included")
_EVIDENCE_FUZZY_KEYWORDS: tuple[str, ...] = ("test", "evidence", "qa", "validation")

_HEADING_RE: re.Pattern[str] = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


class SchemaDriftError(ValueError):
    """Tracker description has a fuzzy-match section signalling intentional restructure.

    Raised by `ensure_section` when the expected section header is missing *and* a
    similarly-named heading exists. The calling skill must hard-stop and ask the
    operator to reconcile; auto-repair would risk a duplicate section or hide the
    operator's intent.
    """


@dataclass(frozen=True)
class SectionRepair:
    """Outcome of `ensure_section`: the (possibly-repaired) description + a repair flag."""

    description: str
    did_repair: bool


def resolve_active_tracker(issues: Iterable[dict]) -> dict | None:
    """Return the newest active release-tracker issue, or None if there are no candidates.

    Args:
        issues: Iterable of JIRA issue dicts as returned by `searchJiraIssuesUsingJql`.
            Each dict must have a `key` and a `fields.created` ISO-8601 timestamp. The
            caller is responsible for the JQL filter (`project = FP AND labels =
            "release-tracker" AND status not in ("READY FOR DEPLOY", DONE)`).

    Returns:
        The newest issue by `fields.created`, or None if `issues` is empty.

    Notes:
        The canonical JQL already orders by created DESC, so the first element is
        normally the winner. We re-sort defensively so callers cannot break the
        contract by passing an unsorted list.
    """
    candidates = list(issues)
    if not candidates:
        return None
    candidates.sort(
        key=lambda issue: issue.get("fields", {}).get("created", ""),
        reverse=True,
    )
    return candidates[0]


def derive_work_type(labels: Iterable[str]) -> str:
    """Return the work-type tag for a child ticket based on its JIRA labels.

    Args:
        labels: The full list of labels on the child ticket (FP-XYZ being worked on,
            not the tracker).

    Returns:
        One of `"tech-debt"`, `"carry-over"`, or `"sprint"` (default when no
        `release-work-type:*` label is present). When multiple work-type labels apply,
        precedence is tech-debt > carry-over > sprint.
    """
    label_set = set(labels)
    for work_type in WORK_TYPE_PRECEDENCE:
        if f"release-work-type:{work_type}" in label_set:
            return work_type
    return "sprint"


def ensure_section(
    description: str,
    header_word: str,
    anchor_header_word: str | None,
    fuzzy_keywords: tuple[str, ...],
) -> SectionRepair:
    """Ensure `## <header_word>` exists; auto-repair on missing, hard-stop on fuzzy-match.

    Implements the schema-drift policy from FP-212 review Q5=C:

    - Section already present → no-op, return original description.
    - Section absent and no fuzzy-match heading exists → insert the section at a
      stable anchor (immediately before `## <anchor_header_word>` if present, else
      append at end-of-description) and return `did_repair=True`.
    - Section absent but a fuzzy-match heading exists → raise `SchemaDriftError` so
      the calling skill can stop and ask the operator to reconcile.

    Args:
        description: Current tracker description text (markdown).
        header_word: Canonical section header word (e.g. `"Bundle"`, `"Test evidence"`).
        anchor_header_word: Header word of the section the new section should precede
            (e.g. `"PR"` for Bundle, `"Known issues"` for Test evidence). None →
            append at end of description.
        fuzzy_keywords: Words that, on a non-canonical heading, signal an intentional
            restructure. Hitting one raises `SchemaDriftError`.

    Returns:
        `SectionRepair(description, did_repair)`.

    Raises:
        SchemaDriftError: A fuzzy-match heading exists, suggesting the operator
            renamed the section deliberately. The skill must surface to the user.
    """
    if _section_present(description, header_word):
        return SectionRepair(description=description, did_repair=False)

    fuzzy_match = _find_fuzzy_heading(description, header_word, fuzzy_keywords)
    if fuzzy_match is not None:
        raise SchemaDriftError(
            f"Found '## {fuzzy_match}' instead of '## {header_word}'. "
            "Please reconcile manually."
        )

    if anchor_header_word is not None:
        anchor_pattern = _header_pattern(anchor_header_word)
        anchor = anchor_pattern.search(description)
        if anchor is not None:
            new_desc = (
                description[: anchor.start()]
                + f"## {header_word}\n\n"
                + description[anchor.start() :]
            )
            return SectionRepair(description=new_desc, did_repair=True)

    # No anchor available (or anchor section missing too): append at end-of-description.
    suffix = "" if description.endswith("\n") else "\n"
    new_desc = description + suffix + f"\n## {header_word}\n"
    return SectionRepair(description=new_desc, did_repair=True)


_BUNDLE_TABLE_HEADER_RE: re.Pattern[str] = re.compile(
    r"^\|.*Jira ID.*\|", re.IGNORECASE | re.MULTILINE
)
_BUNDLE_TABLE_SEPARATOR_RE: re.Pattern[str] = re.compile(
    r"^\|\s*[-:]+\s*\|", re.MULTILINE
)

_BUNDLE_TABLE_HEADER_BLOCK = (
    "| Jira ID | Desc | Type | Status | Document (Y/N) |\n"
    "| --- | --- | --- | --- | --- |\n"
)


def _is_table_section(body: str) -> bool:
    """True if the section body contains a markdown table header."""
    return bool(_BUNDLE_TABLE_HEADER_RE.search(body))


def append_bundle_entry(
    description: str,
    fp_key: str,
    work_type: str,
    summary: str,
    status: str = "In Progress",
) -> str:
    """Append a bundle entry for `fp_key` to the tracker's `## Bundle` section.

    Writes a **table row** when the section already has a table header, creates
    a new table (header + first row) when the section is empty, and falls back
    to the legacy checklist format only when the section has existing checklist
    items (backward compatibility for trackers not yet migrated to table format).

    Idempotent: if any line within the bundle section already contains the
    literal `fp_key` token (word-boundary match — `FP-21` does not match
    `FP-212`), the description is returned unchanged.

    If the bundle section is missing, it is auto-repaired via `ensure_section`
    before the append. A fuzzy-match heading raises `SchemaDriftError`.

    Args:
        description: Current tracker description text.
        fp_key: Child-ticket key (e.g. `"FP-212"`).
        work_type: One of `"sprint"`, `"tech-debt"`, `"carry-over"`.
        summary: One-line ticket summary (no trailing newline).
        status: JIRA status to record in the Status column. Defaults to
            ``"In Progress"`` since `/jira-impl` appends at branch time.

    Returns:
        Updated description text.

    Raises:
        SchemaDriftError: Propagated from `ensure_section` on fuzzy-match.
    """
    description = ensure_section(
        description,
        BUNDLE_HEADER,
        anchor_header_word="PR",
        fuzzy_keywords=_BUNDLE_FUZZY_KEYWORDS,
    ).description

    body_start, body_end = _section_block(description, BUNDLE_HEADER)
    body = description[body_start:body_end]

    if _line_for_fp_key(body, fp_key) is not None:
        return description  # idempotent re-run

    if _is_table_section(body):
        # Table format: append a new row after the existing rows
        new_line = (
            f"| [{fp_key}]({JIRA_BASE_URL}/{fp_key}) "
            f"| {summary} | {work_type} | {status} | |\n"
        )
        new_body = _append_to_section_body(body, new_line)
    elif body.strip():
        # Legacy checklist format: existing items present, keep consistent
        new_line = f"- [ ] {fp_key} [{work_type}] {summary}\n"
        new_body = _append_to_section_body(body, new_line)
    else:
        # Empty section: bootstrap a new table from scratch
        new_body = "\n" + _BUNDLE_TABLE_HEADER_BLOCK + (
            f"| [{fp_key}]({JIRA_BASE_URL}/{fp_key}) "
            f"| {summary} | {work_type} | {status} | |\n"
        ) + "\n"

    return description[:body_start] + new_body + description[body_end:]


def set_document_flag(description: str, fp_key: str) -> str:
    """Set the Document column to ``'Y'`` for `fp_key` in the bundle table.

    Finds the table row for `fp_key` in the ``## Bundle`` section and updates
    the last cell (Document column) to ``Y``. No-op when:

    - The bundle section is missing.
    - No row contains `fp_key`.
    - The row is in legacy checklist format (no Document column).

    Args:
        description: Current tracker description text.
        fp_key: Child-ticket key (e.g. `"FP-212"`).

    Returns:
        Updated description text (unchanged if no table row was found).
    """
    if not _section_present(description, BUNDLE_HEADER):
        return description

    body_start, body_end = _section_block(description, BUNDLE_HEADER)
    body = description[body_start:body_end]

    row_match = _line_for_fp_key(body, fp_key)
    if row_match is None:
        return description

    row_start, row_end = row_match
    row = body[row_start:row_end]

    if not row.lstrip().startswith("|"):
        return description  # legacy checklist row — no Document column

    new_row = _set_last_table_cell(row, "Y")
    new_body = body[:row_start] + new_row + body[row_end:]
    return description[:body_start] + new_body + description[body_end:]


def upsert_evidence_entry(
    description: str,
    fp_key: str,
    run_n: int,
    status_word: str,
    comment_url: str,
) -> str:
    """Insert or replace the evidence line for `<fp_key>` in the Test evidence section.

    Per FP-212 review Q3=B: re-runs of `/jira-test FP-XXX` overwrite the prior tracker
    line for that ticket. The tracker shows one line per FP-XXX; per-run history lives
    on the per-ticket evidence comments themselves, not on the tracker.

    Auto-repairs a missing section via `ensure_section`; fuzzy-match raises
    `SchemaDriftError`.

    Args:
        description: Current tracker description text.
        fp_key: Child-ticket key (e.g. `"FP-212"`).
        run_n: Run number from `/jira-test` (1, 2, …).
        status_word: One of `"Pass"`, `"Fail"`, `"Blocked"`, `"Partial"`.
        comment_url: URL of the per-ticket evidence comment on FP-XXX.

    Returns:
        Updated description text.

    Raises:
        SchemaDriftError: Propagated from `ensure_section` on fuzzy-match.
    """
    description = ensure_section(
        description,
        TEST_EVIDENCE_HEADER,
        anchor_header_word="Known issues",
        fuzzy_keywords=_EVIDENCE_FUZZY_KEYWORDS,
    ).description

    body_start, body_end = _section_block(description, TEST_EVIDENCE_HEADER)
    body = description[body_start:body_end]

    new_line = (
        f"- {fp_key} Run {run_n} _{status_word}_ "
        f"— [evidence comment]({comment_url})\n"
    )

    prior = _line_for_fp_key(body, fp_key)
    if prior is not None:
        line_start, line_end = prior
        new_body = body[:line_start] + new_line + body[line_end:]
    else:
        new_body = _append_to_section_body(body, new_line)

    return description[:body_start] + new_body + description[body_end:]


# --- Internal helpers -------------------------------------------------------------


def _header_pattern(header_word: str) -> re.Pattern[str]:
    """Compile a case-insensitive header-prefix matcher for `## <header_word>...`."""
    return re.compile(
        r"^##\s+" + re.escape(header_word) + r"(\b|$)",
        re.MULTILINE | re.IGNORECASE,
    )


def _section_present(description: str, header_word: str) -> bool:
    """True if a `## <header_word>...` heading exists in `description`."""
    return _header_pattern(header_word).search(description) is not None


def _find_fuzzy_heading(
    description: str,
    canonical_word: str,
    keywords: tuple[str, ...],
) -> str | None:
    """Return the first heading text containing a fuzzy keyword and not the canonical header.

    Returns the heading title (the `<title>` part of `## <title>`) so the caller can
    include it in the error message. Returns None if no fuzzy heading exists.
    """
    canonical_lower = canonical_word.lower()
    for match in _HEADING_RE.finditer(description):
        title = match.group(1)
        title_lower = title.lower()
        # Skip the canonical section itself — `_section_present` is checked separately.
        if title_lower.startswith(canonical_lower):
            continue
        if any(keyword in title_lower for keyword in keywords):
            return title
    return None


def _section_block(description: str, header_word: str) -> tuple[int, int]:
    """Return (body_start, body_end) character offsets for the named section's body.

    `body_start` is the offset of the first character after the header line's newline.
    `body_end` is the offset just before the next `## ` heading, or `len(description)`
    when this is the last section.

    Callers must ensure the section exists first (use `ensure_section` or
    `_section_present`); this helper asserts presence.
    """
    header_line_pattern = re.compile(
        r"^##\s+" + re.escape(header_word) + r".*?\n",
        re.MULTILINE | re.IGNORECASE,
    )
    header = header_line_pattern.search(description)
    assert header is not None, f"section '## {header_word}' must exist before _section_block"
    body_start = header.end()
    next_heading = re.compile(r"^##\s+", re.MULTILINE).search(description, body_start)
    body_end = next_heading.start() if next_heading is not None else len(description)
    return (body_start, body_end)


def _line_for_fp_key(body: str, fp_key: str) -> tuple[int, int] | None:
    """Return (start, end) of the first line in `body` containing literal `fp_key`.

    `end` includes the trailing newline so the caller can splice cleanly. Word-boundary
    match: `FP-21` does not match `FP-212`. Returns None if no line contains `fp_key`.
    """
    pattern = re.compile(r"(?m)^.*\b" + re.escape(fp_key) + r"\b.*(?:\n|$)")
    match = pattern.search(body)
    if match is None:
        return None
    return (match.start(), match.end())


def _append_to_section_body(body: str, new_line: str) -> str:
    """Append `new_line` to a section body, preserving spacing before the next section.

    Strips trailing blank lines so the new entry attaches to existing content, then
    re-adds a single trailing newline so the next `## ` section stays visually
    separated. `new_line` is expected to already end with `\\n`.
    """
    stripped = body.rstrip()
    if stripped:
        return stripped + "\n" + new_line + "\n"
    return new_line + "\n"


def _set_last_table_cell(row: str, value: str) -> str:
    """Replace the last data cell in a markdown table row with `value`.

    Handles the trailing newline transparently.

    Args:
        row: A single markdown table row string, e.g.
            ``"| [FP-212](url) | summary | sprint | Done | |\\n"``.
        value: Replacement value for the last cell (e.g. ``"Y"``).

    Returns:
        Updated row string with the last cell replaced.
    """
    newline = "\n" if row.endswith("\n") else ""
    stripped = row.rstrip("\n")
    parts = stripped.split("|")
    # parts[0] == "" (before first |), parts[-1] == "" (after last |)
    # parts[-2] is the last cell content
    parts[-2] = f" {value} "
    return "|".join(parts) + newline
