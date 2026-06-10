"""Release-document generation package.

Pure data transformation: input is structured tracker data (a ``ReleaseInput``),
output is the rendered release-document markdown. No JIRA dependency — the
Claude slash-command orchestrator fetches tracker data via MCP and hands the
structured input in.

Pipeline: raw bundle tickets → ``clean_summary`` → ``categorize_bundle`` →
(optional polish) → ``render``.

Per-ticket docs pipeline (FP-213 / /jira-done):
    ``PerTicketContext`` → Claude synthesises docs → ``write_per_ticket_docs``
"""

from .categorizer import categorize_bundle
from .cleanup import clean_summary
from .models import (
    BUCKET_ORDER,
    BundleTicket,
    Bucket,
    CarryOverTicket,
    CategorizedBucket,
    CategorizedRelease,
    PRReference,
    ReadinessItem,
    ReleaseInput,
    ReleaseManifest,
    EvidenceLink,
    WorkType,
)
from .polish import (
    Audience,
    GeminiVertexClient,
    PolishClient,
    build_default_client,
    distill_talking_points,
    polish,
)
from .business_renderer import render_business
from .next_tracker import build_next_tracker_body, bump_patch
from .per_ticket_polish import PerTicketContext
from .per_ticket_writer import (
    DocType,
    PerTicketDoc,
    Tag,
    filename_for,
    find_existing_docs,
    make_stub_doc,
    write_per_ticket_docs,
)
from .renderer import render
from .visuals import (
    build_business_mindmap,
    build_business_pie,
    build_components_mermaid,
)

__all__ = [
    "BUCKET_ORDER",
    "Bucket",
    "BundleTicket",
    "CarryOverTicket",
    "CategorizedBucket",
    "CategorizedRelease",
    "DocType",
    "PRReference",
    "PerTicketContext",
    "PerTicketDoc",
    "ReadinessItem",
    "ReleaseInput",
    "ReleaseManifest",
    "EvidenceLink",
    "Tag",
    "WorkType",
    "Audience",
    "GeminiVertexClient",
    "PolishClient",
    "build_business_mindmap",
    "build_business_pie",
    "build_components_mermaid",
    "build_default_client",
    "build_next_tracker_body",
    "bump_patch",
    "categorize_bundle",
    "clean_summary",
    "distill_talking_points",
    "filename_for",
    "find_existing_docs",
    "make_stub_doc",
    "polish",
    "render",
    "render_business",
    "write_per_ticket_docs",
]
