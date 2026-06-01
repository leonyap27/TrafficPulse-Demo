"""Migrate legacy usage events into the two-zone layout.

FP-196 one-time migration helper. Reads every legacy event from:

- `.claude/usage/events.jsonl` (the pre-FP-196 single-file format)
- `.claude/usage/events/YYYY-MM/*.json` (the intermediate per-event-file
  layout shipped in commit `1f78260` and superseded by this ticket)

Groups them by `developer`, then writes each developer's events into their
own `.claude/usage/team/events-<hash>.jsonl` (per-user team profile). Each
developer's historical attribution is preserved.

By default the legacy sources are removed after a successful run so they
do not get rebuilt by stale tooling. Pass `--keep-legacy` to leave them
in place (e.g. for a dry-run inspection).

Idempotent: re-running merges new legacy entries without duplicating
existing team-file lines (dedup on `timestamp+command+outcome+trigger`).
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

import publish_usage  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
USAGE_DIR = REPO_ROOT / ".claude" / "usage"
LEGACY_JSONL = USAGE_DIR / "events.jsonl"
LEGACY_EVENT_FILES_DIR = USAGE_DIR / "events"
TEAM_DIR = USAGE_DIR / "team"


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


def _read_event_files(dirpath: Path) -> list[dict]:
    if not dirpath.is_dir():
        return []
    out: list[dict] = []
    for path in sorted(dirpath.rglob("*.json")):
        if path.name == "index.json":
            continue
        if not path.is_file():
            continue
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            out.append(parsed)
        elif isinstance(parsed, list):
            out.extend(item for item in parsed if isinstance(item, dict))
    return out


def _group_by_developer(events: list[dict]) -> dict[str, list[dict]]:
    buckets: dict[str, list[dict]] = {}
    for event in events:
        dev = event.get("developer") or "unknown"
        buckets.setdefault(dev, []).append(event)
    return buckets


def _merge_into_file(target: Path, new_events: list[dict]) -> tuple[int, int]:
    """Append-merge new events into target JSONL with dedup. Returns (new, total)."""
    existing = _read_jsonl(target)
    seen = {publish_usage._event_dedup_key(e) for e in existing}
    additions: list[dict] = []
    for event in new_events:
        key = publish_usage._event_dedup_key(event)
        if key in seen:
            continue
        seen.add(key)
        additions.append(event)
    if not additions and target.is_file():
        return (0, len(existing))
    merged = existing + additions
    merged.sort(key=lambda e: e.get("timestamp") or "")
    target.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(
        json.dumps(e, ensure_ascii=False, separators=(",", ":")) for e in merged
    )
    target.write_text(body + "\n" if body else "", encoding="utf-8")
    return (len(additions), len(merged))


def migrate(
    jsonl_path: Path,
    event_files_dir: Path,
    team_dir: Path,
    *,
    keep_legacy: bool,
) -> dict[str, tuple[int, int]]:
    """Run the migration. Returns per-developer (new, total) counts."""
    legacy_events = _read_jsonl(jsonl_path) + _read_event_files(event_files_dir)
    if not legacy_events and not keep_legacy:
        return {}

    grouped = _group_by_developer(legacy_events)
    summary: dict[str, tuple[int, int]] = {}
    for developer, events in grouped.items():
        target = publish_usage.team_file_for(developer, team_dir=team_dir)
        new_count, total = _merge_into_file(target, events)
        summary[developer] = (new_count, total)

    if not keep_legacy:
        if jsonl_path.is_file():
            jsonl_path.unlink()
        if event_files_dir.is_dir():
            shutil.rmtree(event_files_dir)

    return summary


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Redistribute legacy usage events into per-user team JSONL files."
    )
    parser.add_argument("--jsonl", type=Path, default=LEGACY_JSONL)
    parser.add_argument(
        "--event-files-dir",
        type=Path,
        default=LEGACY_EVENT_FILES_DIR,
        dest="event_files_dir",
    )
    parser.add_argument("--team-dir", type=Path, default=TEAM_DIR, dest="team_dir")
    parser.add_argument(
        "--keep-legacy",
        action="store_true",
        help="Do not delete legacy events.jsonl + events/ after migration.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    summary = migrate(
        jsonl_path=args.jsonl,
        event_files_dir=args.event_files_dir,
        team_dir=args.team_dir,
        keep_legacy=args.keep_legacy,
    )
    if not summary:
        print("migrate_events_to_files: nothing to migrate")
        return 0
    for developer, (new_count, total) in sorted(summary.items()):
        print(
            f"  {developer}: +{new_count} new event(s); team file has {total}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
