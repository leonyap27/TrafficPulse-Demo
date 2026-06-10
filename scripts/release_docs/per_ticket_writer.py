"""Per-ticket release document writer for /jira-done.

Each completed ticket writes up to three files into
``docs/3.0-deployment/releases/<tracker_key>/``:

    FP-XYZ-<tag>-technical.md   — engineering / ops audience
    FP-XYZ-<tag>-business.md    — user / product audience
    FP-XYZ-<tag>-management.md  — director / sponsor audience

``<tag>`` is one of:

    b  must-have       — always included when /release-cut collects docs
    a  good-to-have    — included by default; can be filtered out
    c  optional/skip   — written as a stub for traceability, excluded from
                         /release-cut output unless explicitly requested

Re-running /jira-done for the same ticket overwrites both files idempotently
(never appends). A missing doc for a given type means the AI assigned tag ``c``
and skipped generation; the stub file ``FP-XYZ-c-<type>.md`` still exists so
``/release-cut`` can detect the skip decision rather than treating it as missing.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

DocType = Literal["technical", "business", "management"]
Tag = Literal["a", "b", "c"]

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_RELEASES_DIR = _REPO_ROOT / "docs" / "3.0-deployment" / "releases"

_STUB_TEMPLATE = """\
<!-- /jira-done: tag={tag} (optional/skip) — AI judged this doc type low-value for this ticket -->
<!-- Re-run /jira-done {ticket_key} to regenerate if the ticket scope changes. -->
"""


@dataclass(frozen=True)
class PerTicketDoc:
    """One rendered document for a specific audience."""

    doc_type: DocType
    tag: Tag
    content: str


def write_per_ticket_docs(
    tracker_key: str,
    ticket_key: str,
    docs: list[PerTicketDoc],
    *,
    releases_dir: Path | None = None,
) -> list[Path]:
    """Write per-ticket docs to ``releases/<tracker_key>/<ticket_key>-<tag>-<type>.md``.

    Idempotent: existing files are overwritten. Missing doc types are not touched —
    callers are responsible for passing all intended docs.

    Args:
        tracker_key: Active release-tracker key (e.g. ``"FP-194"``).
        ticket_key: Completed ticket key (e.g. ``"FP-213"``).
        docs: Sequence of :class:`PerTicketDoc` instances to write.
        releases_dir: Override the default releases directory (used in tests).

    Returns:
        Sorted list of :class:`~pathlib.Path` objects for the files written.
    """
    base = (releases_dir or _DEFAULT_RELEASES_DIR) / tracker_key
    base.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for doc in docs:
        path = base / f"{ticket_key}-{doc.tag}-{doc.doc_type}.md"
        path.write_text(doc.content, encoding="utf-8")
        written.append(path)
    return sorted(written)


def make_stub_doc(ticket_key: str, doc_type: DocType) -> PerTicketDoc:
    """Return a ``c``-tagged stub :class:`PerTicketDoc` for traceability.

    Used when the AI assigns tag ``c`` (optional/skip) so /release-cut can
    detect the skip decision rather than treating the absence as an error.
    """
    return PerTicketDoc(
        doc_type=doc_type,
        tag="c",
        content=_STUB_TEMPLATE.format(tag="c", ticket_key=ticket_key),
    )


def filename_for(ticket_key: str, tag: Tag, doc_type: DocType) -> str:
    """Return the canonical filename for a per-ticket doc (no directory prefix)."""
    return f"{ticket_key}-{tag}-{doc_type}.md"


def find_existing_docs(
    tracker_key: str,
    ticket_key: str,
    *,
    releases_dir: Path | None = None,
) -> dict[DocType, Path]:
    """Return any existing per-ticket doc paths for ``ticket_key`` in ``tracker_key``.

    Useful for detecting whether a prior /jira-done run already wrote files before
    overwriting. Keys are doc types that currently have a file on disk.
    """
    base = (releases_dir or _DEFAULT_RELEASES_DIR) / tracker_key
    found: dict[DocType, Path] = {}
    for doc_type in ("technical", "business", "management"):
        for tag in ("a", "b", "c"):
            path = base / filename_for(ticket_key, tag, doc_type)  # type: ignore[arg-type]
            if path.exists():
                found[doc_type] = path  # type: ignore[index]
                break
    return found
