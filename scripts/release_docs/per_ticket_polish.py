"""Source-material context for per-ticket release docs (/jira-done).

Holds the structured input gathered from JIRA (ticket description, plan comment,
review thread Q&A) before it is used by the /jira-done command to synthesise the
three audience-specific markdown documents (technical / business / management).

No AI client code lives here — doc synthesis is performed by the Claude Code
session executing /jira-done, which writes the results via per_ticket_writer.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PerTicketContext:
    """Source material gathered from JIRA for one ticket's doc generation."""

    ticket_key: str
    summary: str
    bucket: str = "Other"
    description: str = ""
    plan_comment: str = ""
    review_thread: str = ""
    pr_title: str = ""
