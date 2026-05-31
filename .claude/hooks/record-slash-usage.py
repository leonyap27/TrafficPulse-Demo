#!/usr/bin/env python3
"""UserPromptSubmit hook: record a 'started' event for slash-command invocations.

Reads a JSON payload on stdin (Claude Code hook contract), extracts a leading
slash command from the prompt, and calls scripts/record_usage.py to append one
'started' event. Fail-soft — any error path exits 0 so the prompt never breaks.

Hook config lives in .claude/settings.json under `hooks.UserPromptSubmit`.

FP-192.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path


SLASH_COMMAND_RE = re.compile(r"^\s*(/[a-z][a-z0-9-]*)\b", re.IGNORECASE)


def _project_dir() -> Path:
    env_dir = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_dir:
        return Path(env_dir)
    # Hook lives at <repo>/.claude/hooks/, so two levels up is the repo root.
    return Path(__file__).resolve().parent.parent.parent


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    prompt = payload.get("prompt") or ""
    match = SLASH_COMMAND_RE.match(prompt)
    if not match:
        return 0

    command = match.group(1)
    recorder = _project_dir() / "scripts" / "record_usage.py"
    if not recorder.is_file():
        return 0

    env = os.environ.copy()
    env.setdefault("USAGE_PLATFORM", "claude-code")

    try:
        subprocess.run(
            [
                sys.executable,
                str(recorder),
                "--command",
                command,
                "--outcome",
                "started",
                "--trigger",
                "hook",
            ],
            env=env,
            timeout=5,
            check=False,
            capture_output=True,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
