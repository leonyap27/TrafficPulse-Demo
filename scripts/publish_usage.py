"""Publish private live events into the shared per-user team profile.

Reads the developer's private live JSONL at
`~/.claude-usage/<owner>/<repo>/events.jsonl` (written by
`scripts/record_usage.py`) and upserts new entries into the developer's
**own** team profile inside the repo at
`.claude/usage/team/events-<hash>.jsonl`.

Designed to be wired as a Claude Code `Stop` hook so it runs at the end of
every session — no developer action required. The intent is "the data
flows on its own"; the developer's normal `git commit` / `git push` is what
distributes their profile to the team, and `git pull` brings back peers'
updates.

Safety rules (intentionally conservative for a session-end hook):

- A developer may only ever write their own `events-<hash>.jsonl`.
  The filename hash is derived from `git config user.email`.
- The publisher does **not** commit and does **not** push. It only
  rewrites the user's own file and (optionally) `git add`s it so the
  developer's next normal commit carries the team file along.
- Fail-soft: any error path exits 0; the Claude Code session is never
  blocked by a publishing failure.

FP-196.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Optional

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
TEAM_DIR = REPO_ROOT / ".claude" / "usage" / "team"


def _git(args: list[str], cwd: Optional[Path] = None) -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd or REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.warning("git invocation failed: %s", exc)
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def detect_developer_email() -> str:
    """Developer's git email, with environment / OS fallbacks."""
    email = _git(["config", "user.email"])
    if email:
        return email
    return os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"


def user_hash(email: str) -> str:
    """Stable, filename-safe 10-hex-char SHA-1 of the developer's email.

    Short enough for tidy filenames; long enough to make collisions a
    non-issue on a team of dozens. Stored events still carry the raw
    `developer` field — the hash is purely a filename bucket.
    """
    return hashlib.sha1(email.encode("utf-8")).hexdigest()[:10]


def team_file_for(email: str, team_dir: Optional[Path] = None) -> Path:
    """Return the per-developer team JSONL path."""
    base = team_dir if team_dir is not None else TEAM_DIR
    return base / f"events-{user_hash(email)}.jsonl"


def _read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            out.append(parsed)
    return out


def _event_dedup_key(event: dict) -> tuple:
    """Idempotency key.

    `timestamp`+`command`+`outcome`+`trigger` is unique in practice for a
    single developer's stream (the recorder timestamps to second precision
    and slash-command lifecycles do not produce multiple identical events
    inside one second).
    """
    return (
        event.get("timestamp"),
        event.get("command"),
        event.get("outcome"),
        event.get("trigger"),
    )


def _filter_own_events(events: Iterable[dict], email: str) -> list[dict]:
    """Defence in depth: never write events authored by someone else.

    The recorder always stamps `developer` from `git config user.email`,
    so live entries should already be the current user's. We re-check here
    so that an accidentally-shared live directory cannot contaminate
    another developer's profile.
    """
    return [e for e in events if e.get("developer") == email]


def merge_into_team_file(
    live_path: Path,
    target_path: Path,
    email: str,
) -> tuple[int, int]:
    """Upsert live events into the target per-user team file.

    Returns:
        (new_count, total_count) — new lines appended this run, and total
        lines present in the team file after the merge.
    """
    live_events = _filter_own_events(_read_jsonl(live_path), email)
    if not live_events and not target_path.is_file():
        return (0, 0)

    existing = _read_jsonl(target_path)
    seen: set[tuple] = {_event_dedup_key(e) for e in existing}

    new_events: list[dict] = []
    for event in live_events:
        key = _event_dedup_key(event)
        if key in seen:
            continue
        seen.add(key)
        new_events.append(event)

    if not new_events and target_path.is_file():
        # Nothing to publish; leave the file alone (no spurious mtime bump).
        return (0, len(existing))

    target_path.parent.mkdir(parents=True, exist_ok=True)
    merged = existing + new_events
    merged.sort(key=lambda e: e.get("timestamp") or "")
    body = "\n".join(
        json.dumps(e, ensure_ascii=False, separators=(",", ":")) for e in merged
    )
    target_path.write_text(body + "\n" if body else "", encoding="utf-8")
    return (len(new_events), len(merged))


def stage_for_commit(path: Path) -> bool:
    """`git add` the team file so the dev's next commit carries it.

    Returns True on success, False otherwise. Failure is non-fatal: the
    file is still on disk; staging is a convenience.
    """
    if not path.is_file():
        return False
    try:
        rel = path.relative_to(REPO_ROOT)
    except ValueError:
        # Path is outside the repo — refuse to stage.
        return False
    return _git(["add", "--", str(rel)]) is not None or path.is_file()


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish private live events into the shared team profile.",
    )
    parser.add_argument(
        "--live",
        type=Path,
        default=None,
        help="Override the live JSONL path (default: auto-detect).",
    )
    parser.add_argument(
        "--team-dir",
        type=Path,
        default=None,
        dest="team_dir",
        help="Override the team directory (default: .claude/usage/team).",
    )
    parser.add_argument(
        "--email",
        default=None,
        help="Override developer email (default: git config user.email).",
    )
    parser.add_argument(
        "--no-stage",
        action="store_true",
        help="Skip git add of the team file (default: stage on success).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress the one-line summary on stdout.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    try:
        # Resolve email + paths.
        email = args.email or detect_developer_email()

        if args.live is not None:
            live_path = args.live
        else:
            # Import lazily so the recorder module's import side-effects
            # do not run when the publisher is invoked alone.
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            import record_usage  # noqa: WPS433

            live_path = record_usage.live_events_path()

        target_path = team_file_for(email, team_dir=args.team_dir)
        new_count, total_count = merge_into_team_file(live_path, target_path, email)

        if not args.no_stage and new_count > 0:
            stage_for_commit(target_path)

        if not args.quiet:
            print(
                f"publish_usage: +{new_count} new event(s); team file has {total_count}",
                file=sys.stdout,
            )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        # Never break the calling session on a publisher failure.
        print(f"publish_usage: {exc}", file=sys.stderr)
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
