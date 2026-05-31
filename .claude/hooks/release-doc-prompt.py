#!/usr/bin/env python3
"""SessionStart hook: nudge about pending deploy-ledger entries.

Scans .claude/usage/deploy-ledger/pending/. If non-empty, emits an additional
context message so Claude can offer to run /release-doc at the start of the
session. Fail-soft — any error path exits 0 so the session never breaks.

Hook config lives in .claude/settings.json under `hooks.SessionStart`.

FP-188.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _project_dir() -> Path:
    env_dir = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_dir:
        return Path(env_dir)
    # Hook lives at <repo>/.claude/hooks/, so two levels up is the repo root.
    return Path(__file__).resolve().parent.parent.parent


def _pending_entries(repo_root: Path) -> list[dict]:
    pending = repo_root / ".claude" / "usage" / "deploy-ledger" / "pending"
    if not pending.is_dir():
        return []
    entries: list[dict] = []
    for json_file in sorted(pending.glob("*.json")):
        try:
            entries.append(json.loads(json_file.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return entries


def _format_message(entries: list[dict]) -> str:
    bullets = [
        f"- {entry.get('target', '?').upper()} v{entry.get('version', '?')} "
        f"on {entry.get('timestamp', '?')}"
        for entry in entries
    ]
    count = len(entries)
    plural = "deploy" if count == 1 else "deploys"
    return (
        f"**{count} pending {plural} without a release document:**\n"
        + "\n".join(bullets)
        + "\n\nRun `/release-doc` to generate the doc for the oldest entry, "
        "or `/release-doc <tracker-key>` to target a specific tracker. "
        "See `.claude/usage/deploy-ledger/README.md` for the schema."
    )


def main() -> int:
    """Drain stdin (per hook contract) and maybe emit additionalContext."""
    try:
        sys.stdin.read()
    except OSError:
        pass

    try:
        entries = _pending_entries(_project_dir())
    except OSError:
        return 0

    if not entries:
        return 0

    output = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": _format_message(entries),
        }
    }
    print(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
