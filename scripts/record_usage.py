"""Local workflow usage event recorder.

Writes one JSON-lines record per invocation into the **private live zone**
outside the git worktree:

    ~/.claude-usage/<owner>/<repo>/events.jsonl

Used by:
- Claude Code UserPromptSubmit hook (auto-capture of slash-command invocations).
- Workflow command docs (end-of-run outcome enrichment).
- Codex / AGENTS.md bridge (manual call).
- Developers (ad-hoc tracking via direct invocation).

Schema reference: .claude/usage/schema.md
Layout reference: .claude/usage/README.md

Fail-soft by design: any failure is logged to stderr and exits 0 so the
calling workflow is never broken.

FP-196 moved storage out of the git worktree so that branch switches /
stashes / checkouts no longer affect the recorder. Publication of these
events to the shared, in-repo team profile under
`.claude/usage/team/events-<hash>.jsonl` is the job of
`scripts/publish_usage.py`, not this recorder.

Example:
    python scripts/record_usage.py --command /jira-plan --outcome completed

FP-192 (recorder contract); FP-196 (live-zone storage).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent

# The live zone lives outside the git worktree on purpose — see module docstring.
LIVE_ROOT = Path.home() / ".claude-usage"

VALID_OUTCOMES = {"started", "completed", "partial", "blocked", "failed", "skipped"}
VALID_PLATFORMS = {"claude-code", "codex", "other"}
VALID_ASSET_TYPES = {"command", "rule", "hook", "agent", "bridge", "other"}
VALID_TRIGGERS = {"slash-command", "bridge", "manual", "hook", "direct"}
VALID_CANDIDATE_ACTIONS = {"keep", "improve", "demote", "retire", "generalize"}


def _git(args: list[str]) -> Optional[str]:
    """Run a git command, return stripped stdout, or None on failure."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.warning("git invocation failed: %s", exc)
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


_REMOTE_PREFERENCE = ("github", "origin", "upstream")


def _detect_repo() -> str:
    """Derive a stable owner/repo identifier from a GitHub-shaped remote.

    Preference order: github > origin > upstream > any other remote. Skips
    legacy non-GitHub URLs (e.g. CodeCommit) when a GitHub remote exists.
    Falls back to the repo root's basename if no remote can be resolved.
    """
    candidates: list[str] = []
    for name in _REMOTE_PREFERENCE:
        url = _git(["remote", "get-url", name])
        if url:
            candidates.append(url)
    remote_list = _git(["remote"]) or ""
    for name in remote_list.splitlines():
        if name and name not in _REMOTE_PREFERENCE:
            url = _git(["remote", "get-url", name])
            if url:
                candidates.append(url)
    github_re = re.compile(r"github\.com[:/]([\w.\-]+)/([\w.\-]+?)(?:\.git)?/?$")
    for url in candidates:
        match = github_re.search(url)
        if match:
            return f"{match.group(1)}/{match.group(2)}"
    if candidates:
        url = re.sub(r"\.git/?$", "", candidates[0])
        match = re.search(r"[:/]([\w.\-]+)/([\w.\-]+)$", url)
        if match:
            return f"{match.group(1)}/{match.group(2)}"
    return REPO_ROOT.name


def _detect_developer() -> str:
    """Developer identity from git config; fallback to OS username."""
    email = _git(["config", "user.email"])
    if email:
        return email
    return os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"


def _detect_developer_name() -> Optional[str]:
    """JIRA display name for the current developer.

    Reads from ~/.claude-usage/profile.json (display_name key) first —
    set this once so the dashboard shows the real name regardless of what
    git config user.name says on each machine. Falls back to git config
    user.name when no profile exists.
    """
    profile = Path.home() / ".claude-usage" / "profile.json"
    if profile.exists():
        try:
            data = json.loads(profile.read_text())
            name = data.get("display_name", "").strip()
            if name:
                return name
        except Exception:
            pass
    return _git(["config", "user.name"]) or None


def _detect_platform() -> str:
    """Platform from env var, with auto-detection fallback.

    Order:
    1. USAGE_PLATFORM env var (explicit wins — set by each tool's startup).
    2. CLAUDE_PROJECT_DIR env var present -> 'claude-code' (Claude Code
       always sets this, so direct CLI calls from inside a Claude Code
       session get the right platform without needing the env-var prefix).
    3. Otherwise 'other'.

    Codex/other agents that wrap the recorder MUST set `--platform codex`
    (or USAGE_PLATFORM=codex) explicitly — there's no reliable signal to
    auto-detect them from environment alone.
    """
    value = (os.environ.get("USAGE_PLATFORM") or "").strip().lower()
    if value in VALID_PLATFORMS:
        return value
    if os.environ.get("CLAUDE_PROJECT_DIR"):
        return "claude-code"
    return "other"


_COMMAND_PREFIX_TO_ASSET = (
    (".claude/commands/", "command"),
    (".claude/rules/", "rule"),
    (".claude/hooks/", "hook"),
    (".claude/agents/", "agent"),
)
_BRIDGE_PATHS = {".claude/CLAUDE.md", ".claude/ONBOARDING.md", "AGENTS.md"}


def _infer_asset_path(command: str) -> str:
    """Map a slash-command name to its canonical asset file."""
    if command.startswith("/"):
        return f".claude/commands/{command[1:]}.md"
    return command


def _infer_asset_type(asset_path: str) -> str:
    """Classify an asset path into one of the schema's asset_type enum values."""
    if asset_path in _BRIDGE_PATHS:
        return "bridge"
    for prefix, asset_type in _COMMAND_PREFIX_TO_ASSET:
        if asset_path.startswith(prefix):
            return asset_type
    return "other"


def _validate_enum(value: Optional[str], allowed: set[str], field: str) -> Optional[str]:
    if value is None:
        return None
    if value not in allowed:
        raise ValueError(f"invalid {field}: {value!r} (allowed: {sorted(allowed)})")
    return value


def live_events_path(repo_key: Optional[str] = None) -> Path:
    """Return the absolute path to the live JSONL file for this repo.

    The repo key has a `/` (`owner/repo`) which is used as a directory
    separator so each repo gets its own subtree under LIVE_ROOT.
    """
    key = repo_key if repo_key is not None else _detect_repo()
    # Treat the key as path components — owner/repo becomes two directories.
    return LIVE_ROOT.joinpath(*key.split("/")) / "events.jsonl"


def build_event(
    command: str,
    outcome: str,
    *,
    note: Optional[str] = None,
    candidate_action: Optional[str] = None,
    asset_path: Optional[str] = None,
    asset_type: Optional[str] = None,
    trigger: Optional[str] = None,
    platform: Optional[str] = None,
    timestamp: Optional[str] = None,
) -> dict:
    """Construct a validated event dict ready to be appended to the live file."""
    outcome = _validate_enum(outcome, VALID_OUTCOMES, "outcome")  # type: ignore[assignment]
    candidate_action = _validate_enum(candidate_action, VALID_CANDIDATE_ACTIONS, "candidate_action")
    if asset_path is None:
        asset_path = _infer_asset_path(command)
    asset_type = _validate_enum(asset_type or _infer_asset_type(asset_path), VALID_ASSET_TYPES, "asset_type")  # type: ignore[assignment]
    trigger = _validate_enum(trigger or "manual", VALID_TRIGGERS, "trigger")  # type: ignore[assignment]
    platform = _validate_enum(platform or _detect_platform(), VALID_PLATFORMS, "platform")  # type: ignore[assignment]
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    developer_name = _detect_developer_name()
    event: dict = {
        "timestamp": timestamp,
        "repo": _detect_repo(),
        "developer": _detect_developer(),
        "platform": platform,
        "command": command,
        "asset_path": asset_path,
        "asset_type": asset_type,
        "trigger": trigger,
        "outcome": outcome,
        "note": note,
        "candidate_action": candidate_action,
    }
    if developer_name:
        event["developer_name"] = developer_name
    return event


def append_event(event: dict, live_path: Optional[Path] = None) -> Path:
    """Append one event line to the live JSONL file.

    POSIX `open(O_APPEND)` writes smaller than PIPE_BUF (≥4 KiB) are atomic,
    so concurrent recorders on the same machine do not interleave bytes.
    Each event is a single short JSON line, well below that bound.

    Returns:
        Path to the live JSONL file that was appended to.
    """
    target = live_path if live_path is not None else live_events_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        os.write(fd, line.encode("utf-8"))
    finally:
        os.close(fd)
    return target


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Record one usage event to the private live zone.",
    )
    parser.add_argument("--command", required=True, help="Workflow name, e.g. /jira-plan")
    parser.add_argument(
        "--outcome",
        required=True,
        choices=sorted(VALID_OUTCOMES),
        help="Lifecycle state",
    )
    parser.add_argument("--note", default=None, help="Optional human note")
    parser.add_argument(
        "--candidate-action",
        default=None,
        choices=sorted(VALID_CANDIDATE_ACTIONS),
        dest="candidate_action",
    )
    parser.add_argument("--asset-path", default=None, dest="asset_path")
    parser.add_argument(
        "--asset-type",
        default=None,
        choices=sorted(VALID_ASSET_TYPES),
        dest="asset_type",
    )
    parser.add_argument(
        "--trigger",
        default=None,
        choices=sorted(VALID_TRIGGERS),
    )
    parser.add_argument(
        "--platform",
        default=None,
        choices=sorted(VALID_PLATFORMS),
        help="Override platform detection (normally from USAGE_PLATFORM env var)",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    try:
        event = build_event(
            command=args.command,
            outcome=args.outcome,
            note=args.note,
            candidate_action=args.candidate_action,
            asset_path=args.asset_path,
            asset_type=args.asset_type,
            trigger=args.trigger,
            platform=args.platform,
        )
        append_event(event)
    except (OSError, ValueError) as exc:
        # Never break the calling workflow on a recorder failure.
        print(f"record_usage: {exc}", file=sys.stderr)
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
