"""Validate local workflow usage-tracking coverage and hygiene.

Checks enforced by this script:
1. `.claude/usage/inventory.json` matches the current asset scan.
2. Every command doc includes recorder snippets for both `started` and a
   terminal outcome.
3. The merged events from every per-developer team file
   (`.claude/usage/team/events-*.jsonl`) plus the current developer's
   private live JSONL contain valid schema and no stale started events
   beyond the configured age threshold.

Usage:
    python scripts/validate_usage_tracking.py
    python scripts/validate_usage_tracking.py --max-open-hours 1

FP-192 (validator); FP-196 (read from two-zone storage).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import record_usage
import seed_inventory

REPO_ROOT = Path(__file__).resolve().parent.parent
INVENTORY_PATH = REPO_ROOT / ".claude" / "usage" / "inventory.json"
TEAM_DIR = REPO_ROOT / ".claude" / "usage" / "team"
TERMINAL_OUTCOMES = {"completed", "partial", "blocked", "failed", "skipped"}
REQUIRED_EVENT_FIELDS = {
    "timestamp",
    "repo",
    "developer",
    "platform",
    "command",
    "asset_path",
    "asset_type",
    "trigger",
    "outcome",
}


def _load_inventory_entries(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise ValueError("inventory.json missing 'entries' list")
    return entries


def _normalized_inventory_entries(entries: list[dict]) -> set[tuple[str, str, str]]:
    normalized: set[tuple[str, str, str]] = set()
    for entry in entries:
        asset_path = str(entry.get("asset_path", ""))
        asset_type = str(entry.get("asset_type", ""))
        name = str(entry.get("name", ""))
        normalized.add((asset_path, asset_type, name))
    return normalized


def _check_inventory_sync(
    inventory_path: Path,
    errors: list[str],
) -> list[seed_inventory.InventoryEntry]:
    generated_entries = seed_inventory.build_inventory()
    if not inventory_path.is_file():
        errors.append(
            "Missing .claude/usage/inventory.json. Run `python scripts/seed_inventory.py`."
        )
        return generated_entries
    try:
        snapshot_entries = _load_inventory_entries(inventory_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        errors.append(f"Unable to read inventory.json: {exc}")
        return generated_entries

    generated_norm = {
        (entry.asset_path, entry.asset_type, entry.name) for entry in generated_entries
    }
    snapshot_norm = _normalized_inventory_entries(snapshot_entries)

    if generated_norm == snapshot_norm:
        return generated_entries

    missing = sorted(generated_norm - snapshot_norm)
    extra = sorted(snapshot_norm - generated_norm)
    if missing:
        formatted = ", ".join(path for path, _, _ in missing[:5])
        errors.append(f"inventory.json is missing {len(missing)} asset(s): {formatted}")
    if extra:
        formatted = ", ".join(path for path, _, _ in extra[:5])
        errors.append(f"inventory.json has {len(extra)} stale asset(s): {formatted}")
    errors.append("Run `python scripts/seed_inventory.py` to refresh inventory.json.")
    return generated_entries


def _check_command_docs_have_recorder_steps(
    commands: list[seed_inventory.InventoryEntry],
    errors: list[str],
) -> None:
    for command in commands:
        command_path = REPO_ROOT / command.asset_path
        try:
            text = command_path.read_text(encoding="utf-8")
        except OSError as exc:
            errors.append(f"Unable to read {command.asset_path}: {exc}")
            continue

        start_pattern = re.compile(
            rf"record_usage\.py\s+--command\s+{re.escape(command.name)}\s+--outcome\s+started\b"
        )
        terminal_pattern = re.compile(
            rf"record_usage\.py\s+--command\s+{re.escape(command.name)}\s+--outcome\s+"
            r"(?:<state>|completed|partial|blocked|failed|skipped)(?:\s|$)"
        )
        if not start_pattern.search(text):
            errors.append(
                f"{command.asset_path} is missing a `started` recorder snippet for {command.name}."
            )
        if not terminal_pattern.search(text):
            errors.append(
                f"{command.asset_path} is missing a terminal recorder snippet for {command.name}."
            )


def _parse_timestamp(value: str) -> datetime:
    timestamp = datetime.fromisoformat(value)
    if timestamp.tzinfo is None:
        raise ValueError("timestamp must include timezone offset")
    return timestamp


def _iter_event_sources(
    team_dir: Path,
    live_path: Optional[Path],
) -> list[Path]:
    """Return ordered list of JSONL files to validate.

    Order: every per-developer team file in sorted name order, then the
    current developer's live file (if present). Stable so error messages
    referencing 'event N of <file>' are reproducible across runs.
    """
    sources: list[Path] = []
    if team_dir.is_dir():
        sources.extend(sorted(team_dir.glob("events-*.jsonl")))
    if live_path is not None and live_path.is_file():
        sources.append(live_path)
    return sources


def _label_for(path: Path) -> str:
    """Short, repo-relative-ish label for use in validation error messages."""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        # Live zone lives outside the repo; just use the file name.
        return path.name


def _check_events_from_sources(
    sources: list[Path],
    *,
    max_open_hours: float,
    now: datetime,
    known_commands: set[str],
    errors: list[str],
    warnings: list[str],
) -> None:
    if not sources:
        warnings.append(
            "No event sources found (no team/events-*.jsonl files and no live zone). "
            "Nothing to validate — the tracker has not recorded anything yet."
        )
        return

    pending: dict[tuple[str, str, str], list[tuple[str, datetime]]] = {}

    for source in sources:
        label = _label_for(source)
        try:
            lines = source.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            errors.append(f"Unable to read {label}: {exc}")
            continue

        for line_no, raw_line in enumerate(lines, start=1):
            line = raw_line.strip()
            if not line:
                continue
            ref = f"{label} line {line_no}"

            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"{ref} is invalid JSON: {exc}")
                continue

            missing_fields = sorted(REQUIRED_EVENT_FIELDS - set(event))
            if missing_fields:
                errors.append(f"{ref} missing field(s): {', '.join(missing_fields)}")
                continue

            try:
                timestamp = _parse_timestamp(str(event["timestamp"]))
            except ValueError as exc:
                errors.append(f"{ref} has bad timestamp: {exc}")
                continue

            command = str(event["command"])
            developer = str(event["developer"])
            platform = str(event["platform"])
            outcome = str(event["outcome"])
            trigger = str(event["trigger"])
            asset_type = str(event["asset_type"])

            if platform not in record_usage.VALID_PLATFORMS:
                errors.append(f"{ref} has invalid platform: {platform}")
            if outcome not in record_usage.VALID_OUTCOMES:
                errors.append(f"{ref} has invalid outcome: {outcome}")
            if trigger not in record_usage.VALID_TRIGGERS:
                errors.append(f"{ref} has invalid trigger: {trigger}")
            if asset_type not in record_usage.VALID_ASSET_TYPES:
                errors.append(f"{ref} has invalid asset_type: {asset_type}")

            if command.startswith("/") and command not in known_commands:
                warnings.append(
                    f"{ref} references unknown command {command} (asset may have been removed)."
                )

            key = (command, developer, platform)
            if outcome == "started":
                pending.setdefault(key, []).append((ref, timestamp))
                continue

            if outcome in TERMINAL_OUTCOMES:
                open_starts = pending.get(key)
                if open_starts:
                    open_starts.pop(0)
                    if not open_starts:
                        pending.pop(key, None)
                else:
                    warnings.append(
                        f"{ref} has terminal outcome without prior started "
                        f"({command}, {developer}, {platform})."
                    )

    for (command, developer, platform), starts in pending.items():
        for ref, timestamp in starts:
            age_hours = (now - timestamp).total_seconds() / 3600
            if age_hours > max_open_hours:
                errors.append(
                    "Abandoned started event: "
                    f"{ref} ({command}, {developer}, {platform}) is open for {age_hours:.1f}h."
                )
            else:
                warnings.append(
                    "Open started event still within grace period: "
                    f"{ref} ({command}, {developer}, {platform}) age {age_hours:.1f}h."
                )


def validate_tracking(
    *,
    inventory_path: Path = INVENTORY_PATH,
    team_dir: Path = TEAM_DIR,
    live_path: Optional[Path] = None,
    max_open_hours: float = 24.0,
    now: Optional[datetime] = None,
) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for local usage-tracking quality gates.

    By default reads every team file under `team_dir` plus the current
    developer's live JSONL. Tests can pin `team_dir` to a sandbox and
    leave `live_path=None` to validate a single synthetic source.
    """
    errors: list[str] = []
    warnings: list[str] = []

    generated_entries = _check_inventory_sync(inventory_path, errors)
    command_entries = [entry for entry in generated_entries if entry.asset_type == "command"]
    known_commands = {entry.name for entry in command_entries}

    _check_command_docs_have_recorder_steps(command_entries, errors)
    current_time = now or datetime.now(timezone.utc).astimezone()
    resolved_live = live_path if live_path is not None else _detect_default_live_path()
    sources = _iter_event_sources(team_dir, resolved_live)
    _check_events_from_sources(
        sources,
        max_open_hours=max_open_hours,
        now=current_time,
        known_commands=known_commands,
        errors=errors,
        warnings=warnings,
    )
    return errors, warnings


def _detect_default_live_path() -> Optional[Path]:
    """Try to resolve the current developer's live JSONL; None on failure.

    Failure is non-fatal: the validator still runs against the team dir
    even if the live zone can't be resolved (e.g. CI checkout without git
    config user.email set).
    """
    try:
        return record_usage.live_events_path()
    except (OSError, ValueError):
        return None


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate local usage-tracking files for FP-192."
    )
    parser.add_argument(
        "--inventory",
        type=Path,
        default=INVENTORY_PATH,
        help="Path to inventory.json",
    )
    parser.add_argument(
        "--team-dir",
        type=Path,
        default=TEAM_DIR,
        dest="team_dir",
        help="Directory containing per-developer events-<hash>.jsonl files.",
    )
    parser.add_argument(
        "--live-path",
        type=Path,
        default=None,
        dest="live_path",
        help="Override the current developer's live JSONL (default: auto-detect).",
    )
    parser.add_argument(
        "--max-open-hours",
        type=float,
        default=24.0,
        help="Fail when a started event is older than this threshold.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    errors, warnings = validate_tracking(
        inventory_path=args.inventory,
        team_dir=args.team_dir,
        live_path=args.live_path,
        max_open_hours=args.max_open_hours,
    )

    for warning in warnings:
        print(f"WARNING: {warning}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("usage tracking validation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
