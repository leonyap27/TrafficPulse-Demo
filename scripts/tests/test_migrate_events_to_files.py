"""Tests for scripts/migrate_events_to_files.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import migrate_events_to_files as migrate  # noqa: E402
import publish_usage  # noqa: E402


def _event(command: str, developer: str, timestamp: str) -> dict:
    return {
        "timestamp": timestamp,
        "repo": "x/y",
        "developer": developer,
        "platform": "codex",
        "command": command,
        "asset_path": ".claude/commands/jira-review.md",
        "asset_type": "command",
        "trigger": "bridge",
        "outcome": "completed",
        "note": None,
        "candidate_action": None,
    }


def _write_jsonl(path: Path, events: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(json.dumps(e, separators=(",", ":")) for e in events)
    path.write_text(body + "\n" if body else "", encoding="utf-8")


def test_migrate_groups_legacy_jsonl_by_developer(tmp_path):
    source = tmp_path / "events.jsonl"
    events_dir = tmp_path / "events"  # intentionally absent — JSONL only
    team_dir = tmp_path / "team"
    _write_jsonl(
        source,
        [
            _event("/jira-plan", "dev-a@example.com", "2026-05-25T11:00:00+08:00"),
            _event("/jira-impl", "dev-b@example.com", "2026-05-25T12:00:00+08:00"),
            _event("/jira-test", "dev-a@example.com", "2026-05-25T13:00:00+08:00"),
        ],
    )

    summary = migrate.migrate(
        jsonl_path=source,
        event_files_dir=events_dir,
        team_dir=team_dir,
        keep_legacy=False,
    )

    assert summary["dev-a@example.com"] == (2, 2)
    assert summary["dev-b@example.com"] == (1, 1)
    a_file = publish_usage.team_file_for("dev-a@example.com", team_dir=team_dir)
    b_file = publish_usage.team_file_for("dev-b@example.com", team_dir=team_dir)
    assert a_file.read_text(encoding="utf-8").count("\n") == 2
    assert b_file.read_text(encoding="utf-8").count("\n") == 1
    # Legacy source removed.
    assert not source.exists()


def test_migrate_also_reads_per_event_json_files(tmp_path):
    source = tmp_path / "events.jsonl"
    events_dir = tmp_path / "events" / "2026-05"
    events_dir.mkdir(parents=True)
    team_dir = tmp_path / "team"

    event = _event("/jira-plan", "dev@example.com", "2026-05-25T11:00:00+08:00")
    (events_dir / "20260525T110000-abc.json").write_text(json.dumps(event), encoding="utf-8")
    # An index.json should be ignored by the migrator.
    (events_dir.parent / "index.json").write_text(json.dumps({"files": []}), encoding="utf-8")

    summary = migrate.migrate(
        jsonl_path=source,
        event_files_dir=events_dir.parent,
        team_dir=team_dir,
        keep_legacy=False,
    )

    assert summary["dev@example.com"] == (1, 1)
    target = publish_usage.team_file_for("dev@example.com", team_dir=team_dir)
    assert json.loads(target.read_text(encoding="utf-8").strip())["command"] == "/jira-plan"
    # Legacy events directory removed too.
    assert not events_dir.parent.exists()


def test_migrate_is_idempotent(tmp_path):
    source = tmp_path / "events.jsonl"
    team_dir = tmp_path / "team"
    _write_jsonl(
        source,
        [_event("/jira-plan", "dev@example.com", "2026-05-25T11:00:00+08:00")],
    )

    first = migrate.migrate(
        jsonl_path=source,
        event_files_dir=tmp_path / "events",
        team_dir=team_dir,
        keep_legacy=True,
    )
    second = migrate.migrate(
        jsonl_path=source,
        event_files_dir=tmp_path / "events",
        team_dir=team_dir,
        keep_legacy=True,
    )

    assert first["dev@example.com"] == (1, 1)
    assert second["dev@example.com"] == (0, 1)


def test_migrate_keep_legacy_leaves_source_intact(tmp_path):
    source = tmp_path / "events.jsonl"
    team_dir = tmp_path / "team"
    _write_jsonl(
        source,
        [_event("/jira-plan", "dev@example.com", "2026-05-25T11:00:00+08:00")],
    )

    migrate.migrate(
        jsonl_path=source,
        event_files_dir=tmp_path / "events",
        team_dir=team_dir,
        keep_legacy=True,
    )

    assert source.is_file()
