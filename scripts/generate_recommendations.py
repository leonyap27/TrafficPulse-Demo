"""Generate the initial inventory + recommendation report for FP-192.

Reads .claude/usage/inventory.json plus every per-developer team profile
under .claude/usage/team/ and the current developer's private live zone,
then emits a markdown report at .claude/usage/initial-recommendations.md
with:

- Total counts by asset type
- One row per asset with usage signal + a starter candidate action

Recommendation heuristic (intentionally conservative — humans override the
defaults once real usage data accrues):

| Signal                                            | Default action |
|---------------------------------------------------|----------------|
| asset has >= 1 recorded event                     | keep           |
| asset has 0 events, < 14 days since tracker start | keep (probation) |
| asset has 0 events, >= 14 days since tracker start | demote         |

Re-run this after the tracker has accumulated data to refresh the list.

FP-192.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

import record_usage  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
INVENTORY_PATH = REPO_ROOT / ".claude" / "usage" / "inventory.json"
TEAM_DIR = REPO_ROOT / ".claude" / "usage" / "team"
LEGACY_EVENTS_PATH = REPO_ROOT / ".claude" / "usage" / "events.jsonl"
DEFAULT_OUTPUT = REPO_ROOT / ".claude" / "usage" / "initial-recommendations.md"
PROBATION_DAYS = 14


def _load_inventory() -> list[dict]:
    if not INVENTORY_PATH.is_file():
        return []
    return json.loads(INVENTORY_PATH.read_text()).get("entries", [])


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


def _dedup_key(event: dict) -> tuple:
    return (
        event.get("timestamp"),
        event.get("command"),
        event.get("outcome"),
        event.get("trigger"),
        event.get("developer"),
    )


def _load_events() -> list[dict]:
    """Merge every team file with the current dev's live zone, with dedup.

    Falls back to the legacy `events.jsonl` only if no team file exists —
    this keeps the recommendation script useful during the migration
    window from FP-196.
    """
    seen: set[tuple] = set()
    merged: list[dict] = []

    if TEAM_DIR.is_dir():
        for path in sorted(TEAM_DIR.glob("events-*.jsonl")):
            for event in _read_jsonl(path):
                key = _dedup_key(event)
                if key in seen:
                    continue
                seen.add(key)
                merged.append(event)

    try:
        live_path = record_usage.live_events_path()
    except OSError:
        live_path = None
    if live_path is not None:
        for event in _read_jsonl(live_path):
            key = _dedup_key(event)
            if key in seen:
                continue
            seen.add(key)
            merged.append(event)

    if not merged:
        # Migration fallback: pick up legacy `.claude/usage/events.jsonl`
        # if it still exists in this checkout.
        for event in _read_jsonl(LEGACY_EVENTS_PATH):
            key = _dedup_key(event)
            if key in seen:
                continue
            seen.add(key)
            merged.append(event)

    return merged


def _earliest_event_date(events: list[dict]) -> Optional[datetime]:
    timestamps: list[datetime] = []
    for ev in events:
        ts = ev.get("timestamp")
        if not ts:
            continue
        try:
            timestamps.append(datetime.fromisoformat(ts))
        except ValueError:
            continue
    return min(timestamps) if timestamps else None


def _recommend(event_count: int, days_since_start: int) -> tuple[str, str]:
    """Return (candidate_action, rationale) for one asset."""
    if event_count >= 1:
        return ("keep", f"{event_count} event(s) recorded")
    if days_since_start < PROBATION_DAYS:
        return ("keep", f"no events yet, but tracker started <{PROBATION_DAYS}d ago — probation")
    return ("demote", f"no events in {days_since_start}d since tracker start")


def build_report(inventory: list[dict], events: list[dict], generated_at: datetime) -> str:
    """Return the markdown report body."""
    earliest = _earliest_event_date(events) or generated_at
    days_since_start = max(0, (generated_at - earliest).days)

    def event_count(asset: dict) -> int:
        """Count events matching this asset by either command name or asset_path."""
        name = asset["name"]
        path = asset["asset_path"]
        return sum(
            1
            for e in events
            if e.get("command") == name or e.get("asset_path") == path
        )

    by_type: dict[str, list[dict]] = {}
    for item in inventory:
        by_type.setdefault(item["asset_type"], []).append(item)

    lines: list[str] = []
    lines.append("# Local Workflow Asset — Initial Recommendation List")
    lines.append("")
    lines.append(f"Generated: `{generated_at.isoformat(timespec='seconds')}`  ")
    lines.append(f"Inventory entries: **{len(inventory)}**  ")
    lines.append(f"Events recorded so far: **{len(events)}**  ")
    lines.append(f"Days since first recorded event: **{days_since_start}**  ")
    lines.append(f"Probation window: **{PROBATION_DAYS} days**")
    lines.append("")
    lines.append(
        "This is the FP-192 baseline. The recommendations below are conservative defaults "
        "— after real usage data accumulates, re-run `scripts/generate_recommendations.py` "
        "(or override directly in the dashboard) to refresh actions. Every asset starts on "
        "`keep` so the team has a chance to use it; assets with no event after the probation "
        "window flip to `demote` for review."
    )
    lines.append("")
    lines.append("## Summary by asset type")
    lines.append("")
    lines.append("| Type | Count | With ≥1 event | Stale |")
    lines.append("|---|---:|---:|---:|")
    for asset_type in sorted(by_type.keys()):
        items = by_type[asset_type]
        used = sum(1 for it in items if event_count(it) > 0)
        stale = len(items) - used
        lines.append(f"| {asset_type} | {len(items)} | {used} | {stale} |")
    lines.append("")

    for asset_type in sorted(by_type.keys()):
        lines.append(f"## {asset_type}")
        lines.append("")
        lines.append("| Asset | Path | Events | Recommendation | Rationale |")
        lines.append("|---|---|---:|---|---|")
        for item in sorted(by_type[asset_type], key=lambda i: i["asset_path"]):
            n = event_count(item)
            action, rationale = _recommend(n, days_since_start)
            lines.append(
                f"| `{item['name']}` | `{item['asset_path']}` | {n} | `{action}` | {rationale} |"
            )
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "Re-generate with: `python scripts/generate_recommendations.py`. "
        "Live dashboard: open `.claude/usage/viewer/index.html` from the filesystem."
    )
    return "\n".join(lines) + "\n"


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Emit initial recommendation report.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    inventory = _load_inventory()
    events = _load_events()
    report = build_report(inventory, events, datetime.now(timezone.utc).astimezone())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    try:
        display = args.output.relative_to(REPO_ROOT)
    except ValueError:
        display = args.output
    print(f"wrote {display} ({len(inventory)} assets, {len(events)} events)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
