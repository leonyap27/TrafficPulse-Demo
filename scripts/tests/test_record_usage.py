"""Tests for scripts/record_usage.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import record_usage  # noqa: E402


@pytest.fixture
def live_zone(tmp_path, monkeypatch):
    """Redirect the live zone to a tmp path keyed by a fake repo identifier."""
    monkeypatch.setattr(record_usage, "LIVE_ROOT", tmp_path / "claude-usage")
    monkeypatch.setattr(record_usage, "_detect_repo", lambda: "owner/repo")
    return record_usage.live_events_path()


def test_build_event_populates_required_fields(monkeypatch):
    monkeypatch.setenv("USAGE_PLATFORM", "claude-code")
    event = record_usage.build_event(command="/jira-plan", outcome="completed")
    assert event["command"] == "/jira-plan"
    assert event["outcome"] == "completed"
    assert event["platform"] == "claude-code"
    assert event["asset_path"] == ".claude/commands/jira-plan.md"
    assert event["asset_type"] == "command"
    assert event["trigger"] == "manual"
    assert event["repo"]
    assert event["developer"]
    assert event["timestamp"]


def test_infer_asset_path_from_slash_command():
    assert record_usage._infer_asset_path("/jira-review") == ".claude/commands/jira-review.md"
    assert record_usage._infer_asset_path("rag-architect") == "rag-architect"


def test_infer_asset_type_handles_each_prefix():
    assert record_usage._infer_asset_type(".claude/commands/x.md") == "command"
    assert record_usage._infer_asset_type(".claude/rules/y.md") == "rule"
    assert record_usage._infer_asset_type(".claude/hooks/z.sh") == "hook"
    assert record_usage._infer_asset_type(".claude/agents/a.md") == "agent"
    assert record_usage._infer_asset_type("AGENTS.md") == "bridge"
    assert record_usage._infer_asset_type(".claude/CLAUDE.md") == "bridge"
    assert record_usage._infer_asset_type("random/path.py") == "other"


def test_build_event_rejects_invalid_outcome():
    with pytest.raises(ValueError, match="invalid outcome"):
        record_usage.build_event(command="/jira-plan", outcome="nonsense")


def test_build_event_rejects_invalid_candidate_action():
    with pytest.raises(ValueError, match="invalid candidate_action"):
        record_usage.build_event(
            command="/jira-plan", outcome="completed", candidate_action="bogus"
        )


def test_platform_defaults_to_other_when_env_unset(monkeypatch):
    monkeypatch.delenv("USAGE_PLATFORM", raising=False)
    event = record_usage.build_event(command="/jira-plan", outcome="completed")
    assert event["platform"] == "other"


def test_platform_override_arg_wins_over_env(monkeypatch):
    monkeypatch.setenv("USAGE_PLATFORM", "codex")
    event = record_usage.build_event(
        command="/jira-plan", outcome="completed", platform="claude-code"
    )
    assert event["platform"] == "claude-code"


def test_live_events_path_uses_owner_repo_as_directories(monkeypatch, tmp_path):
    monkeypatch.setattr(record_usage, "LIVE_ROOT", tmp_path / "claude-usage")
    monkeypatch.setattr(record_usage, "_detect_repo", lambda: "leonyap27/Funding_paper_agent")
    path = record_usage.live_events_path()
    assert path == tmp_path / "claude-usage" / "leonyap27" / "Funding_paper_agent" / "events.jsonl"


def test_append_event_creates_live_file_and_appends_one_line(live_zone):
    event = record_usage.build_event(command="/jira-plan", outcome="completed")
    target = record_usage.append_event(event)
    assert target == live_zone
    lines = live_zone.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["command"] == "/jira-plan"


def test_append_event_is_append_only(live_zone):
    record_usage.append_event(record_usage.build_event(command="/a", outcome="started"))
    record_usage.append_event(record_usage.build_event(command="/b", outcome="completed"))
    lines = live_zone.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["command"] == "/a"
    assert json.loads(lines[1])["command"] == "/b"


def test_append_event_never_touches_in_repo_paths(live_zone):
    """Regression guard: the recorder must not write under .claude/usage/ anymore."""
    in_repo_legacy = record_usage.REPO_ROOT / ".claude" / "usage" / "events.jsonl"
    in_repo_dir = record_usage.REPO_ROOT / ".claude" / "usage" / "events"
    record_usage.append_event(
        record_usage.build_event(command="/jira-plan", outcome="completed")
    )
    assert not in_repo_legacy.exists()
    assert not in_repo_dir.exists()


def test_main_returns_zero_on_invalid_outcome(live_zone, capsys):
    # argparse rejects the bad choice before build_event is reached;
    # the CLI surface should still be locked down.
    with pytest.raises(SystemExit) as exc_info:
        record_usage.main(["--command", "/jira-plan", "--outcome", "weird"])
    assert exc_info.value.code != 0
    captured = capsys.readouterr()
    assert "invalid choice" in captured.err


def test_main_returns_zero_when_write_fails(monkeypatch, live_zone, capsys):
    """Recorder must be fail-soft: a write failure must not crash the caller."""

    def boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(record_usage, "append_event", boom)
    rc = record_usage.main(["--command", "/jira-plan", "--outcome", "completed"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "record_usage" in captured.err
