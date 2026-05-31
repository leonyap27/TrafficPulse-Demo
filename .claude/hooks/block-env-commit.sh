#!/usr/bin/env python3
"""PreToolUse hook: block .env / .env.<env> files from being staged or committed.

Reads JSON on stdin with shape: {"tool_input": {"command": "..."}}.
Exits 0 to allow, 2 to block (stderr message is shown to the user).

Uses shlex to parse shell quoting properly and skips values that follow
flags like -m / -F so commit message bodies never trigger a false positive.
Allows .env.example, .env.sample, .env.template templates.
"""

import json
import shlex
import sys


FLAGS_WITH_VALUE = {
    "-m", "-F", "--file", "-c", "-C",
    "--reuse-message", "--reedit-message",
    "--author", "--date", "--cleanup", "--pathspec-from-file",
}
ALLOWED_BASENAMES = {".env.example", ".env.sample", ".env.template"}


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    command = payload.get("tool_input", {}).get("command", "")
    if not command:
        return 0

    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        return 0
    if not tokens:
        return 0

    # Only inspect `git add` / `git commit`.
    git_idx = -1
    for i, t in enumerate(tokens):
        if t == "git" and i + 1 < len(tokens) and tokens[i + 1] in ("add", "commit"):
            git_idx = i + 1
            break
    if git_idx == -1:
        return 0

    blocked = []
    i = git_idx + 1
    while i < len(tokens):
        t = tokens[i]

        if t in FLAGS_WITH_VALUE:
            i += 2
            continue
        if t.startswith("--") and "=" in t:
            i += 1
            continue
        if t.startswith("-"):
            i += 1
            continue

        base = t.rsplit("/", 1)[-1]
        if base == ".env" or (base.startswith(".env.") and base not in ALLOWED_BASENAMES):
            blocked.append(t)
        i += 1

    if blocked:
        sys.stderr.write("Blocked by .claude/hooks/block-env-commit.sh:\n")
        sys.stderr.write(f"  .env files must not be staged or committed: {' '.join(blocked)}\n")
        sys.stderr.write("  Use .env.example / .env.sample / .env.template for shareable templates.\n")
        sys.stderr.write("  If you need to commit a non-secret env file, rename it first.\n")
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
