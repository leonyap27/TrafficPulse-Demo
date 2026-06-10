"""Tests for scripts/publish_usage.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import publish_usage  # noqa: E402


def _event(
    command: str,
    outcome: str = "completed",
    *,
    timestamp: str = "2026-05-25T11:00:00+08:00",
    developer: str = "leonyap.work@gmail.com",
    trigger: str = "manual",
) -> dict:
    return {
        "timestamp": timestamp,
        "repo": "leonyap27/Funding_paper_agent",
        "developer": developer,
        "platform": "claude-code",
        "command": command,
        "asset_path": f".claude/commands/{command.lstrip('/')}.md",
        "asset_type": "command",
        "trigger": trigger,
        "outcome": outcome,
        "note": None,
        "candidate_action": None,
    }


def _write_jsonl(path: Path, events: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(json.dumps(e, separators=(",", ":")) for e in events)
    path.write_text(body + "\n" if body else "", encoding="utf-8")


def test_user_hash_is_stable_per_email():
    assert publish_usage.user_hash("a@b.com") == publish_usage.user_hash("a@b.com")
    assert publish_usage.user_hash("a@b.com") != publish_usage.user_hash("c@d.com")


def test_user_hash_uses_only_filename_safe_characters():
    # 10 hex chars: digits + a-f only.
    h = publish_usage.user_hash("dev@example.com")
    assert len(h) == 10
    assert all(c in "0123456789abcdef" for c in h)


def test_team_file_path_uses_hash(tmp_path):
    team_dir = tmp_path / "team"
    path = publish_usage.team_file_for("dev@example.com", team_dir=team_dir)
    assert path.parent == team_dir
    assert path.name.startswith("events-")
    assert path.name.endswith(".jsonl")
    # And the hash inside matches the helper.
    expected_hash = publish_usage.user_hash("dev@example.com")
    assert path.name == f"events-{expected_hash}.jsonl"


def test_merge_writes_new_events_to_new_team_file(tmp_path):
    live = tmp_path / "live.jsonl"
    target = tmp_path / "team" / "events-abc.jsonl"
    events = [
        _event("/jira-plan", "started"),
        _event("/jira-plan", "completed", timestamp="2026-05-25T11:00:05+08:00"),
    ]
    _write_jsonl(live, events)

    new, total = publish_usage.merge_into_team_file(live, target, "leonyap.work@gmail.com")

    assert (new, total) == (2, 2)
    written = target.read_text(encoding="utf-8").splitlines()
    assert len(written) == 2
    assert json.loads(written[0])["outcome"] == "started"
    assert json.loads(written[1])["outcome"] == "completed"


def test_merge_is_idempotent_on_repeated_runs(tmp_path):
    live = tmp_path / "live.jsonl"
    target = tmp_path / "team" / "events-abc.jsonl"
    events = [_event("/jira-plan", "completed")]
    _write_jsonl(live, events)

    first = publish_usage.merge_into_team_file(live, target, "leonyap.work@gmail.com")
    second = publish_usage.merge_into_team_file(live, target, "leonyap.work@gmail.com")

    assert first == (1, 1)
    assert second == (0, 1)
    assert target.read_text(encoding="utf-8").splitlines() == [
        json.dumps(events[0], separators=(",", ":")),
    ]


def test_merge_refuses_to_write_other_developers_events(tmp_path):
    """Defence-in-depth: only the current dev's own events ever land in their file."""
    live = tmp_path / "live.jsonl"
    target = tmp_path / "team" / "events-abc.jsonl"
    events = [
        _event("/jira-plan", developer="leonyap.work@gmail.com"),
        _event("/jira-plan", developer="someone-else@example.com"),
    ]
    _write_jsonl(live, events)

    new, total = publish_usage.merge_into_team_file(live, target, "leonyap.work@gmail.com")

    assert (new, total) == (1, 1)
    line = json.loads(target.read_text(encoding="utf-8").strip())
    assert line["developer"] == "leonyap.work@gmail.com"


def test_merge_preserves_chronological_order(tmp_path):
    live = tmp_path / "live.jsonl"
    target = tmp_path / "team" / "events-abc.jsonl"
    _write_jsonl(target, [_event("/jira-plan", "started", timestamp="2026-05-25T10:00:00+08:00")])
    _write_jsonl(
        live,
        [
            _event("/jira-plan", "completed", timestamp="2026-05-25T09:00:00+08:00"),
            _event("/jira-plan", "completed", timestamp="2026-05-25T12:00:00+08:00"),
        ],
    )

    new, total = publish_usage.merge_into_team_file(live, target, "leonyap.work@gmail.com")

    assert (new, total) == (2, 3)
    lines = target.read_text(encoding="utf-8").splitlines()
    timestamps = [json.loads(line)["timestamp"] for line in lines]
    assert timestamps == sorted(timestamps)


def test_merge_handles_missing_live_file_gracefully(tmp_path):
    live = tmp_path / "no-such.jsonl"
    target = tmp_path / "team" / "events-abc.jsonl"
    new, total = publish_usage.merge_into_team_file(live, target, "dev@example.com")
    assert (new, total) == (0, 0)
    assert not target.exists()


def test_main_runs_without_error_when_live_missing(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(publish_usage, "TEAM_DIR", tmp_path / "team")
    rc = publish_usage.main(
        [
            "--live",
            str(tmp_path / "missing.jsonl"),
            "--team-dir",
            str(tmp_path / "team"),
            "--email",
            "dev@example.com",
            "--no-stage",
        ]
    )
    assert rc == 0
    captured = capsys.readouterr()
    assert "publish_usage" in captured.out
