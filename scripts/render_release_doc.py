#!/usr/bin/env python3
"""Render release document(s) from structured tracker data.

This CLI is the deterministic renderer half of FP-188. The Claude
`/release-doc` slash-command orchestrator builds the JSON input by fetching
the tracker via MCP, then invokes this script. Run standalone with
``--input <file.json>`` for testing or for users who already maintain their
own release-data pipeline.

Two output flavours, selected via ``--audience``:
- ``technical`` (default) — engineering-facing doc with FP-XXX keys,
  buckets, PR refs, test evidence, readiness checklist, rollback.
- ``business`` — manager-facing doc with Summary / Talking points /
  flat What-shipped list. Strips engineering detail.
- ``both`` — renders both. Business output path is derived from
  ``--output`` by inserting ``_business`` before the extension (so
  ``FP-194.md`` → ``FP-194_business.md`` alongside it).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make the release_docs package importable from the scripts/ flat layout.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from release_docs import (  # noqa: E402
    CategorizedRelease,
    PolishClient,
    ReleaseInput,
    build_default_client,
    categorize_bundle,
    distill_talking_points,
    polish,
    render,
    render_business,
)

_NO_INPUT_HELP = """\
No input provided. This renderer needs structured tracker data as JSON.

Two ways to provide it:
  1. Run inside Claude Code: `/release-doc <tracker-key>` — the slash command
     fetches the tracker via MCP and pipes the JSON in for you.
  2. Run standalone: `python scripts/render_release_doc.py --input path.json`
     See scripts/release_docs/SAMPLE_INPUT.json for the schema.

This script intentionally has no JIRA dependency, so it cannot fetch tracker
data on its own from a plain terminal.
"""


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render release document(s) from structured tracker data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Path to JSON file with ReleaseInput data. Omit to read from stdin.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "Path to write the technical rendered markdown. Omit to write to "
            "stdout. For --audience business, this is reused as the business "
            "output path; for --audience both, the business output is derived "
            "by inserting '.business' before the extension."
        ),
    )
    parser.add_argument(
        "--audience",
        choices=("technical", "business", "both"),
        default="technical",
        help="Which doc(s) to render. Default: technical.",
    )
    parser.add_argument(
        "--generated-at",
        default=None,
        dest="generated_at",
        help="ISO-8601 timestamp for the audit footer. Defaults to now (UTC).",
    )
    parser.add_argument(
        "--polish",
        action="store_true",
        help=(
            "Run LLM polish (Vertex Gemini) over the bullets. Requires "
            "GOOGLE_CLOUD_PROJECT env var. Falls back to raw bullets per-bucket "
            "if a bucket's polish call fails. For --audience business, also "
            "distills talking points from the polished bullets."
        ),
    )
    parser.add_argument(
        "--extras-file",
        type=Path,
        default=None,
        dest="extras_file",
        help=(
            "Path to a markdown file containing extra release-doc visuals "
            "(sequence diagram, swimlane, decision table) chosen by the host "
            "LLM orchestrating /release-doc. Content is injected verbatim "
            "into the technical doc between the always-on components diagram "
            "and the What-shipped section. Ignored by the business doc. "
            "Omit when no extras are warranted (e.g. bugfix-only bundles) — "
            "covers FP-200 AC4. Renderer does not validate the content; the "
            "host LLM is responsible for well-formed markdown."
        ),
    )
    return parser.parse_args(argv)


def _load_input(path: Path | None) -> ReleaseInput:
    if path is None:
        if sys.stdin.isatty():
            sys.stderr.write(_NO_INPUT_HELP)
            raise SystemExit(2)
        raw = sys.stdin.read()
    else:
        raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    return ReleaseInput.model_validate(data)


def _derive_business_output(technical_output: Path | None) -> Path | None:
    """For --audience both: derive the business output path from the technical one.

    Uses the ``_business`` suffix (e.g. ``FP-194.md`` → ``FP-194_business.md``)
    so the business doc sits next to its technical sibling in the same
    ``releases/v<version>/`` subdirectory. The underscore (not a dot) makes
    the relationship visually obvious in directory listings.
    """
    if technical_output is None:
        return None
    return technical_output.with_name(
        technical_output.stem + "_business" + technical_output.suffix
    )


def _write_output(content: str, output: Path | None) -> None:
    if output is None:
        sys.stdout.write(content)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")


def _load_extras(path: Path | None) -> str | None:
    if path is None:
        return None
    return path.read_text(encoding="utf-8")


def _render_technical(
    categorized: CategorizedRelease,
    client: PolishClient | None,
    generated_at: str | None,
    extras_content: str | None,
) -> str:
    polished = polish(categorized, client=client, audience="technical")
    return render(polished, generated_at=generated_at, extras_content=extras_content)


def _render_business(
    categorized: CategorizedRelease,
    client: PolishClient | None,
    generated_at: str | None,
) -> str:
    polished = polish(categorized, client=client, audience="business")
    bullets = [
        ticket.summary
        for bucket in polished.buckets
        for ticket in bucket.tickets
    ]
    talking_points = distill_talking_points(bullets, client=client)
    return render_business(
        polished,
        talking_points=talking_points,
        generated_at=generated_at,
    )


def main(argv: list[str] | None = None) -> int:
    """Render the requested release doc(s) from input JSON to output path(s) or stdout."""
    args = _parse_args(argv)
    release_input = _load_input(args.input)
    categorized = CategorizedRelease(
        input=release_input,
        buckets=categorize_bundle(release_input.bundle),
    )
    polish_client: PolishClient | None = build_default_client() if args.polish else None
    extras_content = _load_extras(args.extras_file)

    if args.audience in ("technical", "both"):
        rendered = _render_technical(
            categorized, polish_client, args.generated_at, extras_content
        )
        _write_output(rendered, args.output)

    if args.audience in ("business", "both"):
        rendered = _render_business(categorized, polish_client, args.generated_at)
        # technical reuses --output as-is; business reuses for audience=business,
        # but for audience=both it derives a sibling path.
        business_output = (
            _derive_business_output(args.output)
            if args.audience == "both"
            else args.output
        )
        _write_output(rendered, business_output)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
