"""LLM polish step for release-doc bullets + talking-point distillation.

Calls Vertex AI / Gemini via ``google.genai``. Two operations:

1. ``polish_lines`` — rewrite each bullet, preserving line count and order.
   ``audience="technical"`` keeps factual engineering framing; ``audience=
   "business"`` strips FP-XXX, file paths, jargon and frames as user/system
   outcomes for a non-engineer audience.

2. ``distill_talking_points`` — synthesise N bullets down to <= K talking
   points for an executive briefing. Free-form count, thematic grouping
   allowed, factual fidelity required.

The polish client is injectable so unit tests run deterministically without
hitting Vertex. The CLI builds a real client at call time.
"""

from __future__ import annotations

import logging
import os
from typing import Literal, Protocol

from .models import BundleTicket, CategorizedBucket, CategorizedRelease

logger = logging.getLogger(__name__)

Audience = Literal["technical", "business"]

_TECHNICAL_PROMPT_TEMPLATE = """\
Rewrite each release-document bullet below for the **{bucket}** section.
Audience: an engineer reading the release notes — wants to know *what changed*
in plain English, not the raw JIRA title.

Rewrite rules:
- Output EXACTLY {n} lines, one per input line, in the same order.
- One rewritten sentence per line. No bullet markers, no numbering, no commentary.
- Use past or present tense (not imperative). Preserve specific identifiers
  (file names, version numbers, FP-XXX keys) if they appear in the input.
- Do not invent facts beyond what each input line states.
- Do not merge or split lines.

INPUT (one bullet per line):
{joined}

OUTPUT (one rewritten bullet per line, exactly {n} lines):
"""

_BUSINESS_PROMPT_TEMPLATE = """\
Rewrite each release-document bullet below for a business / executive audience.
Audience: a manager or stakeholder who needs to know *what improved for users
or the system* — not engineering detail.

Rewrite rules:
- Output EXACTLY {n} lines, one per input line, in the same order.
- Frame as a delivered outcome ("Improved X", "Added support for Y",
  "Hardened Z", "Enabled W").
- Remove all FP-XXX issue keys, work-type tags ([sprint]/[tech-debt]),
  PR numbers, file paths, internal acronyms.
- Past or present tense, not imperative.
- Plain English. No jargon a non-engineer wouldn't recognise.
- Do not invent facts beyond what each input line states.
- Do not merge or split lines.

INPUT (one bullet per line):
{joined}

OUTPUT (one rewritten bullet per line, exactly {n} lines, business audience):
"""

_TALKING_POINTS_PROMPT_TEMPLATE = """\
You are summarising a software release for an executive briefing. Below is
the list of changes that landed in this release window, one per line.

Write {target_count} or fewer talking-point bullets — short statements a
manager could read aloud in a quarterly review or use as slide bullets.

Rules:
- Output {target_count} or fewer lines, one talking point per line.
- No bullet markers, no numbering, no commentary. Just the text.
- Frame each as a delivered outcome ("Improved ...", "Added ...", "Hardened
  ...").
- Synthesise across multiple input lines if they describe one larger theme.
- Skip changes that aren't material to a high-level audience.
- Do not invent facts beyond what the input states.

CHANGES:
{joined}

TALKING POINTS:
"""


class PolishClient(Protocol):
    """Protocol for the polish operations. Implementations may hit Vertex
    or be a stub for tests."""

    def polish_lines(
        self,
        *,
        bucket: str,
        lines: list[str],
        audience: Audience = "technical",
    ) -> list[str]: ...

    def distill_talking_points(
        self,
        *,
        lines: list[str],
        target_count: int = 5,
    ) -> list[str]: ...


class GeminiVertexClient:
    """Polish client backed by Vertex AI Gemini via ``google.genai``."""

    def __init__(self, *, model: str | None = None) -> None:
        """Initialize the Vertex client. May raise if env config is missing.

        Reads:
            ``GOOGLE_CLOUD_PROJECT`` — required for Vertex.
            ``GOOGLE_CLOUD_LOCATION`` — defaults to ``us-central1`` via SDK.
            ``FP_POLISH_MODEL`` — model id; defaults to ``gemini-1.5-flash-002``.

        Sets ``GOOGLE_GENAI_USE_VERTEXAI=True`` if not already set.
        """
        from google import genai

        os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "True")
        self._client = genai.Client(vertexai=True)
        self._model = model or os.environ.get("FP_POLISH_MODEL", "gemini-1.5-flash-002")

    def polish_lines(
        self,
        *,
        bucket: str,
        lines: list[str],
        audience: Audience = "technical",
    ) -> list[str]:
        template = (
            _BUSINESS_PROMPT_TEMPLATE if audience == "business" else _TECHNICAL_PROMPT_TEMPLATE
        )
        prompt = template.format(
            bucket=bucket,
            n=len(lines),
            joined="\n".join(lines),
        )
        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
        )
        text = (response.text or "").strip()
        return [line.strip() for line in text.splitlines() if line.strip()]

    def distill_talking_points(
        self,
        *,
        lines: list[str],
        target_count: int = 5,
    ) -> list[str]:
        prompt = _TALKING_POINTS_PROMPT_TEMPLATE.format(
            target_count=target_count,
            joined="\n".join(lines),
        )
        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
        )
        text = (response.text or "").strip()
        cleaned = [_strip_bullet_marker(line) for line in text.splitlines() if line.strip()]
        return [line for line in cleaned if line][:target_count]


def _strip_bullet_marker(line: str) -> str:
    stripped = line.strip()
    for marker in ("- ", "* ", "• "):
        if stripped.startswith(marker):
            return stripped[len(marker):].strip()
    # Numbered list ("1. foo", "1) foo")
    if len(stripped) > 2 and stripped[0].isdigit():
        rest = stripped[1:].lstrip("0123456789")
        if rest[:2] in (". ", ") "):
            return rest[2:].strip()
    return stripped


def _polish_bucket(
    client: PolishClient,
    bucket: CategorizedBucket,
    audience: Audience,
) -> CategorizedBucket:
    if not bucket.tickets:
        return bucket
    raw_lines = [t.summary for t in bucket.tickets]
    try:
        polished = client.polish_lines(
            bucket=bucket.bucket, lines=raw_lines, audience=audience
        )
    except Exception as exc:  # noqa: BLE001 - polish must never crash render; fall back to raw
        logger.warning(
            "Polish failed for bucket %s (%s); using raw bullets",
            bucket.bucket,
            exc,
        )
        return bucket
    if len(polished) != len(raw_lines):
        logger.warning(
            "Polish returned %d lines for bucket %s (expected %d); using raw bullets",
            len(polished),
            bucket.bucket,
            len(raw_lines),
        )
        return bucket
    new_tickets = [
        BundleTicket(
            key=t.key,
            work_type=t.work_type,
            summary=polished[i],
            components=t.components,
            labels=t.labels,
            parent_epic_key=t.parent_epic_key,
            parent_epic_summary=t.parent_epic_summary,
        )
        for i, t in enumerate(bucket.tickets)
    ]
    return CategorizedBucket(bucket=bucket.bucket, tickets=new_tickets)


def polish(
    categorized: CategorizedRelease,
    *,
    client: PolishClient | None = None,
    audience: Audience = "technical",
) -> CategorizedRelease:
    """Rewrite bucket bullets via LLM polish.

    Args:
        categorized: Categorized release data.
        client: Injectable polish client. When ``None`` the input is returned
            unchanged (no LLM call).
        audience: Polish prompt mode. ``technical`` keeps engineering framing;
            ``business`` strips identifiers and frames as user outcomes.

    Returns:
        Categorized release with polished bullets per bucket. Buckets where the
        polish call failed or returned the wrong line count keep their raw
        bullets — polish is best-effort by design.
    """
    if client is None:
        return categorized
    polished_buckets = [_polish_bucket(client, b, audience) for b in categorized.buckets]
    return CategorizedRelease(input=categorized.input, buckets=polished_buckets)


def distill_talking_points(
    bullets: list[str],
    *,
    client: PolishClient | None = None,
    target_count: int = 5,
) -> list[str]:
    """Synthesise bullets into <= ``target_count`` executive-briefing bullets.

    Args:
        bullets: Source bullets (typically the business-polished bullets from
            every bucket, concatenated).
        client: Injectable polish client. When ``None``, returns ``[]`` — the
            caller should treat absent talking points as "skip the section".
        target_count: Upper bound on talking-point bullets. Defaults to 5.

    Returns:
        Talking-point bullets, at most ``target_count``. Returns ``[]`` on
        client error so the renderer can render an empty section gracefully.
    """
    if client is None or not bullets:
        return []
    try:
        return client.distill_talking_points(lines=bullets, target_count=target_count)
    except Exception as exc:  # noqa: BLE001 - never crash render
        logger.warning("Talking-points distillation failed (%s); omitting section", exc)
        return []


def build_default_client() -> PolishClient:
    """Construct the production polish client. Raises if Vertex env is missing.

    Called only when ``--polish`` is requested on the CLI. Tests inject their
    own ``PolishClient`` via ``polish(..., client=fake)`` and never call this.
    """
    return GeminiVertexClient()
