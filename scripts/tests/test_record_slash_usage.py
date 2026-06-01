"""Tests for .claude/hooks/record-slash-usage.py (subprocess-based).

Uses a fake recorder script under a tmp CLAUDE_PROJECT_DIR so no real
live-events file is touched during the test run.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent.parent / ".claude" / "hooks" / "record-slash-usage.py"

_FAKE_RECORDER = """\
import sys
from pathlib import Path
Path(__file__).parent.parent.joinpath("recorder-calls.txt").open("a").write(
    " ".join(sys.argv[1:]) + "\\n"
)
"""


def _setup_project(tmp_path: Path) -> Path:
    """Create a minimal fake project dir with a recorder that logs its args."""
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "record_usage.py").write_text(_FAKE_RECORDER)
    return tmp_path


def _run(payload: dict, project_dir: Path | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["USAGE_PLATFORM"] = "claude-code"
    if project_dir is not None:
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
    )


def test_slash_command_calls_recorder(tmp_path: Path):
    project_dir = _setup_project(tmp_path)
    result = _run({"prompt": "/jira-plan FP-199"}, project_dir=project_dir)
    assert result.returncode == 0
    calls = (project_dir / "recorder-calls.txt").read_text()
    assert "--command" in calls
    assert "/jira-plan" in calls
    assert "--outcome" in calls
    assert "started" in calls
    assert "--trigger" in calls
    assert "hook" in calls


def test_non_slash_prompt_does_not_call_recorder(tmp_path: Path):
    project_dir = _setup_project(tmp_path)
    result = _run({"prompt": "just a normal message"}, project_dir=project_dir)
    assert result.returncode == 0
    assert not (project_dir / "recorder-calls.txt").exists()


def test_empty_prompt_does_not_call_recorder(tmp_path: Path):
    project_dir = _setup_project(tmp_path)
    result = _run({"prompt": ""}, project_dir=project_dir)
    assert result.returncode == 0
    assert not (project_dir / "recorder-calls.txt").exists()


def test_missing_prompt_key_does_not_call_recorder(tmp_path: Path):
    project_dir = _setup_project(tmp_path)
    result = _run({}, project_dir=project_dir)
    assert result.returncode == 0
    assert not (project_dir / "recorder-calls.txt").exists()


def test_malformed_json_exits_clean():
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input="not json",
        capture_output=True,
        text=True,
        env={**os.environ, "USAGE_PLATFORM": "claude-code"},
    )
    assert result.returncode == 0


def test_missing_recorder_exits_clean(tmp_path: Path):
    # CLAUDE_PROJECT_DIR points to an empty dir — no scripts/record_usage.py
    result = _run({"prompt": "/jira-plan FP-test"}, project_dir=tmp_path)
    assert result.returncode == 0
