"""Tests for scripts/generate_recommendations.py."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import generate_recommendations as gr  # noqa: E402


def _asset(name, path, asset_type="command"):
    return {"name": name, "asset_path": path, "asset_type": asset_type, "description": None}


def _event(command, asset_path, timestamp="2026-05-24T20:00:00+08:00"):
    return {
        "timestamp": timestamp,
        "repo": "x/y",
        "developer": "dev@example.com",
        "platform": "claude-code",
        "command": command,
        "asset_path": asset_path,
        "asset_type": "command",
        "trigger": "hook",
        "outcome": "completed",
        "note": None,
        "candidate_action": None,
    }


def test_recommend_keeps_assets_with_events():
    action, rationale = gr._recommend(event_count=3, days_since_start=30)
    assert action == "keep"
    assert "3 event" in rationale


def test_recommend_keeps_during_probation_window():
    action, _ = gr._recommend(event_count=0, days_since_start=5)
    assert action == "keep"


def test_recommend_demotes_after_probation_window():
    action, _ = gr._recommend(event_count=0, days_since_start=gr.PROBATION_DAYS)
    assert action == "demote"


def test_event_count_dedupes_command_and_asset_path_match():
    """A single event that matches by BOTH command name AND asset_path is counted once."""
    inventory = [_asset("/jira-plan", ".claude/commands/jira-plan.md")]
    events = [_event("/jira-plan", ".claude/commands/jira-plan.md")]
    report = gr.build_report(inventory, events, datetime.now(timezone.utc).astimezone())
    # The detail row for /jira-plan should report `| ... | 1 | ...`, never `| ... | 2 |`
    assert "| 1 | `keep` | 1 event(s) recorded |" in report


def test_event_count_zero_for_uninventoried_command():
    inventory = [_asset("/jira-plan", ".claude/commands/jira-plan.md")]
    events = [_event("/jira-test", ".claude/commands/jira-test.md")]
    report = gr.build_report(inventory, events, datetime.now(timezone.utc).astimezone())
    assert "| 0 | `keep`" in report


def test_main_writes_markdown_report(tmp_path, monkeypatch):
    output = tmp_path / "report.md"
    rc = gr.main(["--output", str(output)])
    assert rc == 0
    text = output.read_text()
    assert "# Local Workflow Asset" in text
    assert "## Summary by asset type" in text


def test_load_events_merges_team_files_and_live_zone(tmp_path, monkeypatch):
    team_dir = tmp_path / "team"
    team_dir.mkdir()
    (team_dir / "events-aaaa.jsonl").write_text(
        json.dumps(_event("/jira-plan", ".claude/commands/jira-plan.md")) + "\n",
        encoding="utf-8",
    )
    (team_dir / "events-bbbb.jsonl").write_text(
        json.dumps(
            _event(
                "/jira-impl",
                ".claude/commands/jira-impl.md",
                timestamp="2026-05-25T09:00:00+08:00",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    live_path = tmp_path / "live.jsonl"
    live_path.write_text(
        json.dumps(
            _event(
                "/jira-review",
                ".claude/commands/jira-review.md",
                timestamp="2026-05-25T15:00:00+08:00",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(gr, "TEAM_DIR", team_dir)
    monkeypatch.setattr(gr, "LEGACY_EVENTS_PATH", tmp_path / "events.jsonl")
    monkeypatch.setattr(gr.record_usage, "live_events_path", lambda: live_path)

    loaded = gr._load_events()
    commands = sorted(e["command"] for e in loaded)
    assert commands == ["/jira-impl", "/jira-plan", "/jira-review"]


def test_load_events_dedupes_overlap_between_team_and_live(tmp_path, monkeypatch):
    """An event published into both the live zone and the team file shouldn't double-count."""
    team_dir = tmp_path / "team"
    team_dir.mkdir()
    same = _event("/jira-plan", ".claude/commands/jira-plan.md")
    (team_dir / "events-aaaa.jsonl").write_text(
        json.dumps(same) + "\n", encoding="utf-8"
    )
    live_path = tmp_path / "live.jsonl"
    live_path.write_text(json.dumps(same) + "\n", encoding="utf-8")

    monkeypatch.setattr(gr, "TEAM_DIR", team_dir)
    monkeypatch.setattr(gr, "LEGACY_EVENTS_PATH", tmp_path / "events.jsonl")
    monkeypatch.setattr(gr.record_usage, "live_events_path", lambda: live_path)

    loaded = gr._load_events()
    assert len(loaded) == 1


def test_load_events_falls_back_to_legacy_jsonl_when_no_team_or_live(tmp_path, monkeypatch):
    legacy_path = tmp_path / "events.jsonl"
    legacy_path.write_text(json.dumps(_event("/jira-test", ".claude/commands/jira-test.md")) + "\n")

    monkeypatch.setattr(gr, "TEAM_DIR", tmp_path / "team")
    monkeypatch.setattr(gr, "LEGACY_EVENTS_PATH", legacy_path)
    monkeypatch.setattr(gr.record_usage, "live_events_path", lambda: tmp_path / "no-live.jsonl")

    loaded = gr._load_events()
    assert len(loaded) == 1
    assert loaded[0]["command"] == "/jira-test"
