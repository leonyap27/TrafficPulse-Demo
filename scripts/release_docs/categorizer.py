"""Deterministic categorization of bundle tickets into release-doc buckets.

Decision order:
    1. JIRA ``components`` (most reliable signal when set).
    2. Labels (heuristic backup).
    3. Parent epic key/summary (project-specific fallback).
    4. ``Other`` (explicitly flagged so reviewers notice).
"""

from __future__ import annotations

from collections import defaultdict

from .models import BUCKET_ORDER, Bucket, BundleTicket, CategorizedBucket

_COMPONENT_TO_BUCKET: dict[str, Bucket] = {
    "frontend": "Frontend",
    "ui": "Frontend",
    "react": "Frontend",
    "web": "Frontend",
    "backend": "Backend",
    "api": "Backend",
    "fastapi": "Backend",
    "server": "Backend",
    "agents": "Agents+RAG",
    "rag": "Agents+RAG",
    "kb": "Agents+RAG",
    "knowledge-base": "Agents+RAG",
    "knowledge_base": "Agents+RAG",
    "llm": "Agents+RAG",
    "infra": "Infra",
    "infrastructure": "Infra",
    "deployment": "Infra",
    "deploy": "Infra",
    "gcp": "Infra",
    "cloud-run": "Infra",
    "docker": "Infra",
    "ops": "Infra",
    "tooling": "Infra",
    "security": "Security",
    "auth": "Security",
    "iam": "Security",
    "docs": "Docs",
    "documentation": "Docs",
}

_LABEL_TO_BUCKET: dict[str, Bucket] = {
    "security": "Security",
    "auth": "Security",
    "documentation": "Docs",
    "docs": "Docs",
    "frontend": "Frontend",
    "backend": "Backend",
    "infra": "Infra",
    "rag": "Agents+RAG",
}

_PARENT_EPIC_TO_BUCKET: dict[str, Bucket] = {
    # FP-89 "Deployment & Operation" — release-governance work lives here.
    "FP-89": "Infra",
    # FP-183 "Release Version Control and Dev-to-UAT Governance" — children
    # are release-tracker schema, versioning standard, frontend version
    # display, release-doc generation, rollout playbook — all infra-flavoured.
    "FP-183": "Infra",
    # FP-162 "Set up separate DEV deployment environment on GCP" — children
    # are SA provisioning, Cloud Run scripts, secret manager wiring.
    "FP-162": "Infra",
}


def categorize_ticket(ticket: BundleTicket) -> Bucket:
    """Return the bucket for a single ticket using the decision order above.

    Args:
        ticket: A bundle ticket with components/labels/parent metadata.

    Returns:
        The chosen bucket name. ``Other`` when nothing matches.
    """
    for component in ticket.components:
        bucket = _COMPONENT_TO_BUCKET.get(component.strip().lower())
        if bucket:
            return bucket
    for label in ticket.labels:
        bucket = _LABEL_TO_BUCKET.get(label.strip().lower())
        if bucket:
            return bucket
    if ticket.parent_epic_key:
        bucket = _PARENT_EPIC_TO_BUCKET.get(ticket.parent_epic_key)
        if bucket:
            return bucket
    return "Other"


def categorize_bundle(tickets: list[BundleTicket]) -> list[CategorizedBucket]:
    """Categorize and group tickets in the canonical bucket order.

    Buckets with no tickets are omitted. Within a bucket, ticket order is
    preserved from the input (the orchestrator controls input order — usually
    the order they appear in the tracker bundle).

    Args:
        tickets: All bundle tickets for the release.

    Returns:
        Categorized buckets in ``BUCKET_ORDER``. Empty buckets are dropped.
    """
    grouped: dict[Bucket, list[BundleTicket]] = defaultdict(list)
    for ticket in tickets:
        grouped[categorize_ticket(ticket)].append(ticket)
    return [
        CategorizedBucket(bucket=bucket, tickets=grouped[bucket])
        for bucket in BUCKET_ORDER
        if grouped[bucket]
    ]
