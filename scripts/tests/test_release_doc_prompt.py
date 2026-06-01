"""Tests for .claude/hooks/release-doc-prompt.py (subprocess-based).

Uses tmp_path to set up fake deploy-ledger/pending directories so the
real repo state is never touched.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent.parent / ".claude" / "hooks" / "release-doc-prompt.py"


def _pending_dir(tmp_path: Path) -> Path:
    pending = tmp_path / ".claude" / "usage" / "deploy-ledger" / "pending"
    pending.mkdir(parents=True)
    return pending


def _run(project_dir: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["CLAUDE_PROJECT_DIR"] = str(project_dir)
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input="",
        capture_output=True,
        text=True,
        env=env,
    )


def test_empty_pending_dir_produces_no_output(tmp_path: Path):
    _pending_dir(tmp_path)
    result = _run(tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_no_pending_dir_produces_no_output(tmp_path: Path):
    # Pending dir doesn't exist at all
    result = _run(tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_one_entry_emits_additional_context(tmp_path: Path):
    pending = _pending_dir(tmp_path)
    entry = {"version": "0.4.6", "target": "uat", "timestamp": "2026-05-31T00:00:00+08:00"}
    (pending / "deploy-001.json").write_text(json.dumps(entry))

    result = _run(tmp_path)
    assert result.returncode == 0
    output = json.loads(result.stdout)
    context = output["hookSpecificOutput"]["additionalContext"]
    assert "0.4.6" in context
    assert "/release-doc" in context
    assert "UAT" in context


def test_one_entry_singular_deploy_label(tmp_path: Path):
    pending = _pending_dir(tmp_path)
    entry = {"version": "0.4.7", "target": "uat", "timestamp": "2026-05-31T00:00:00+08:00"}
    (pending / "deploy-001.json").write_text(json.dumps(entry))

    result = _run(tmp_path)
    output = json.loads(result.stdout)
    context = output["hookSpecificOutput"]["additionalContext"]
    assert "1 pending deploy" in context


def test_multiple_entries_plural_label(tmp_path: Path):
    pending = _pending_dir(tmp_path)
    for i in range(3):
        entry = {"version": f"0.4.{i}", "target": "uat", "timestamp": "2026-05-31T00:00:00+08:00"}
        (pending / f"deploy-{i:03d}.json").write_text(json.dumps(entry))

    result = _run(tmp_path)
    output = json.loads(result.stdout)
    context = output["hookSpecificOutput"]["additionalContext"]
    assert "3 pending deploys" in context


def test_malformed_json_entry_skipped(tmp_path: Path):
    pending = _pending_dir(tmp_path)
    (pending / "bad.json").write_text("not json at all")

    result = _run(tmp_path)
    assert result.returncode == 0
    # Only malformed entry — skipped, so no pending entries → no output
    assert result.stdout.strip() == ""


def test_mixed_valid_and_malformed_entries(tmp_path: Path):
    pending = _pending_dir(tmp_path)
    (pending / "bad.json").write_text("not json")
    entry = {"version": "0.4.9", "target": "uat", "timestamp": "2026-05-31T00:00:00+08:00"}
    (pending / "good.json").write_text(json.dumps(entry))

    result = _run(tmp_path)
    assert result.returncode == 0
    output = json.loads(result.stdout)
    context = output["hookSpecificOutput"]["additionalContext"]
    # Only the valid entry counts
    assert "1 pending deploy" in context
