"""Tests for scripts/validate_usage_tracking.py (FP-196 two-zone variant)."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import publish_usage  # noqa: E402
import seed_inventory  # noqa: E402
import validate_usage_tracking as vut  # noqa: E402


@pytest.fixture
def usage_sandbox(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()

    commands_dir = repo / ".claude" / "commands"
    usage_dir = repo / ".claude" / "usage"
    team_dir = usage_dir / "team"
    commands_dir.mkdir(parents=True)
    usage_dir.mkdir(parents=True)
    team_dir.mkdir(parents=True)

    command_path = commands_dir / "jira-plan.md"
    command_path.write_text(
        "\n".join(
            [
                "start:",
                "python scripts/record_usage.py --command /jira-plan --outcome started --trigger slash-command",
                "end:",
                "python scripts/record_usage.py --command /jira-plan --outcome <state>",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    generated_entries = [
        seed_inventory.InventoryEntry(
            asset_path=".claude/commands/jira-plan.md",
            asset_type="command",
            name="/jira-plan",
            description=None,
        )
    ]
    monkeypatch.setattr(vut.seed_inventory, "build_inventory", lambda: generated_entries)
    monkeypatch.setattr(vut, "REPO_ROOT", repo)

    inventory_path = usage_dir / "inventory.json"
    inventory_payload = {
        "generated_at": "2026-05-25T00:00:00+08:00",
        "count": 1,
        "entries": [
            {
                "asset_path": ".claude/commands/jira-plan.md",
                "asset_type": "command",
                "name": "/jira-plan",
                "description": None,
            }
        ],
    }
    inventory_path.write_text(json.dumps(inventory_payload), encoding="utf-8")

    now = datetime(2026, 5, 25, 8, 0, tzinfo=timezone(timedelta(hours=8)))
    started_ts = (now - timedelta(minutes=10)).isoformat(timespec="seconds")
    completed_ts = (now - timedelta(minutes=1)).isoformat(timespec="seconds")
    events = [
        {
            "timestamp": started_ts,
            "repo": "x/y",
            "developer": "dev@example.com",
            "platform": "codex",
            "command": "/jira-plan",
            "asset_path": ".claude/commands/jira-plan.md",
            "asset_type": "command",
            "trigger": "bridge",
            "outcome": "started",
            "note": None,
            "candidate_action": None,
        },
        {
            "timestamp": completed_ts,
            "repo": "x/y",
            "developer": "dev@example.com",
            "platform": "codex",
            "command": "/jira-plan",
            "asset_path": ".claude/commands/jira-plan.md",
            "asset_type": "command",
            "trigger": "bridge",
            "outcome": "completed",
            "note": None,
            "candidate_action": None,
        },
    ]
    team_file = publish_usage.team_file_for("dev@example.com", team_dir=team_dir)
    team_file.write_text(
        "\n".join(json.dumps(event, separators=(",", ":")) for event in events) + "\n",
        encoding="utf-8",
    )

    return {
        "repo": repo,
        "inventory_path": inventory_path,
        "team_dir": team_dir,
        "team_file": team_file,
        "command_path": command_path,
        "now": now,
    }


def test_validate_tracking_passes_for_well_formed_inputs(usage_sandbox):
    errors, warnings = vut.validate_tracking(
        inventory_path=usage_sandbox["inventory_path"],
        team_dir=usage_sandbox["team_dir"],
        live_path=None,
        now=usage_sandbox["now"],
        max_open_hours=24.0,
    )
    assert errors == []
    assert warnings == []


def test_validate_tracking_flags_missing_terminal_snippet(usage_sandbox):
    usage_sandbox["command_path"].write_text(
        "python scripts/record_usage.py --command /jira-plan --outcome started\n",
        encoding="utf-8",
    )
    errors, _warnings = vut.validate_tracking(
        inventory_path=usage_sandbox["inventory_path"],
        team_dir=usage_sandbox["team_dir"],
        live_path=None,
        now=usage_sandbox["now"],
    )
    assert any("missing a terminal recorder snippet" in error for error in errors)


def test_validate_tracking_flags_inventory_drift(usage_sandbox):
    usage_sandbox["inventory_path"].write_text(
        json.dumps({"generated_at": "x", "count": 0, "entries": []}),
        encoding="utf-8",
    )
    errors, _warnings = vut.validate_tracking(
        inventory_path=usage_sandbox["inventory_path"],
        team_dir=usage_sandbox["team_dir"],
        live_path=None,
        now=usage_sandbox["now"],
    )
    assert any("inventory.json is missing" in error for error in errors)


def test_validate_tracking_flags_abandoned_started_event(usage_sandbox):
    stale_ts = (usage_sandbox["now"] - timedelta(hours=30)).isoformat(timespec="seconds")
    stale_event = {
        "timestamp": stale_ts,
        "repo": "x/y",
        "developer": "dev@example.com",
        "platform": "codex",
        "command": "/jira-plan",
        "asset_path": ".claude/commands/jira-plan.md",
        "asset_type": "command",
        "trigger": "bridge",
        "outcome": "started",
        "note": None,
        "candidate_action": None,
    }
    usage_sandbox["team_file"].write_text(
        json.dumps(stale_event, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    errors, _warnings = vut.validate_tracking(
        inventory_path=usage_sandbox["inventory_path"],
        team_dir=usage_sandbox["team_dir"],
        live_path=None,
        now=usage_sandbox["now"],
        max_open_hours=24.0,
    )
    assert any("Abandoned started event" in error for error in errors)


def test_validate_tracking_merges_team_and_live_event_sources(usage_sandbox):
    """A `started` on the team file paired with a `completed` only in the live
    zone must close — the validator merges both source streams before pairing.
    """
    # Remove the completed event from the team file (drop second line).
    started_line = usage_sandbox["team_file"].read_text(encoding="utf-8").splitlines()[0]
    usage_sandbox["team_file"].write_text(started_line + "\n", encoding="utf-8")

    live_path = usage_sandbox["repo"] / "live.jsonl"
    completed_ts = (usage_sandbox["now"] - timedelta(minutes=1)).isoformat(timespec="seconds")
    live_event = {
        "timestamp": completed_ts,
        "repo": "x/y",
        "developer": "dev@example.com",
        "platform": "codex",
        "command": "/jira-plan",
        "asset_path": ".claude/commands/jira-plan.md",
        "asset_type": "command",
        "trigger": "bridge",
        "outcome": "completed",
        "note": None,
        "candidate_action": None,
    }
    live_path.write_text(
        json.dumps(live_event, separators=(",", ":")) + "\n", encoding="utf-8"
    )

    errors, warnings = vut.validate_tracking(
        inventory_path=usage_sandbox["inventory_path"],
        team_dir=usage_sandbox["team_dir"],
        live_path=live_path,
        now=usage_sandbox["now"],
        max_open_hours=24.0,
    )

    # The pair started→completed crosses sources but must still be paired.
    assert errors == []
    assert all("Abandoned" not in w for w in warnings)
