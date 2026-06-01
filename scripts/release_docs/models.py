"""Pydantic models for the release-document JSON contract.

The Claude slash-command orchestrator constructs a ``ReleaseInput`` from the
tracker description + per-ticket JIRA metadata, then hands it to the renderer.
Keeping this contract in Pydantic means the renderer cannot silently swallow
malformed inputs from the orchestrator.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

WorkType = Literal["sprint", "tech-debt", "carry-over"]
Bucket = Literal[
    "Frontend",
    "Backend",
    "Agents+RAG",
    "Infra",
    "Security",
    "Docs",
    "Other",
]
ReadinessStatus = Literal["pending", "passed"]

BUCKET_ORDER: tuple[Bucket, ...] = (
    "Frontend",
    "Backend",
    "Agents+RAG",
    "Infra",
    "Security",
    "Docs",
    "Other",
)


class ReleaseManifest(BaseModel):
    """Header fields for the release."""

    model_config = ConfigDict(extra="forbid")

    version: str
    target_env: str
    target_env_detail: str
    release_date: str
    approver: str
    sprint: str | None = None
    uat_owner: str | None = None
    pm: str | None = None


class BundleTicket(BaseModel):
    """One linked ticket included in this release."""

    model_config = ConfigDict(extra="forbid")

    key: str
    work_type: WorkType
    summary: str
    components: list[str] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)
    parent_epic_key: str | None = None
    parent_epic_summary: str | None = None


class CarryOverTicket(BaseModel):
    """A bundle item that did not reach `DONE` this sprint and rolls forward.

    Surfaced in the release doc's `Carry-over to next sprint` section per
    FP-198 so managers see at a glance what's still in flight. The `status`
    field is the ticket's JIRA workflow status at sprint close (e.g.
    `In Review`, `In Progress`, `To Do`), captured verbatim from JIRA.

    `has_doc` is True when `/jira-done` ran and per-ticket release docs exist
    in the current sprint folder. `/release-cut` uses this to auto-run
    `/jira-done` for the new sprint folder when the item is carried over.
    """

    model_config = ConfigDict(extra="forbid")

    key: str
    summary: str
    status: str
    has_doc: bool = False


class PRReference(BaseModel):
    """A PR or commit reference attached to the release."""

    model_config = ConfigDict(extra="forbid")

    repo: str | None = None
    pr_number: int | None = None
    commit_sha: str | None = None
    note: str | None = None


class ReadinessItem(BaseModel):
    """One row of the release readiness checklist."""

    model_config = ConfigDict(extra="forbid")

    label: str
    status: ReadinessStatus


class EvidenceLink(BaseModel):
    """One test-evidence reference for the release tracker."""

    model_config = ConfigDict(extra="forbid")

    label: str
    url: str | None = None


class ReleaseInput(BaseModel):
    """Structured tracker data passed from the orchestrator to the renderer."""

    model_config = ConfigDict(extra="forbid")

    tracker_key: str
    tracker_url: str
    jira_base_url: str
    manifest: ReleaseManifest
    change_summary: list[str]
    bundle: list[BundleTicket]
    pr_references: list[PRReference] = Field(default_factory=list)
    readiness: list[ReadinessItem] = Field(default_factory=list)
    test_evidence: list[EvidenceLink] = Field(default_factory=list)
    known_issues: list[str] = Field(default_factory=list)
    previous_version: str | None = None
    carry_over: list[CarryOverTicket] = Field(default_factory=list)


class CategorizedBucket(BaseModel):
    """All tickets that fell into one bucket, in stable order."""

    model_config = ConfigDict(extra="forbid")

    bucket: Bucket
    tickets: list[BundleTicket]


class CategorizedRelease(BaseModel):
    """``ReleaseInput`` projected through the categorizer."""

    model_config = ConfigDict(extra="forbid")

    input: ReleaseInput
    buckets: list[CategorizedBucket]
